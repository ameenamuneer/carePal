"""
Camera Pan Controller for CarePAL.

Manages three camera tracking modes:
  - TRACKING      : Face/body tracking using YOLOv8n. Pans to keep the
                    subject nearest to frame center within the frame.
                    Falls back to LOOK_AROUND if no subject is seen for
                    NO_SUBJECT_TIMEOUT seconds.
  - LOOK_AROUND   : Slowly sweeps the camera left and right until a
                    subject is detected, then transitions to TRACKING.
  - MANUAL_OVERRIDE: Accepts explicit pan commands from the AI orchestrator.
                    Reverts to TRACKING after MANUAL_OVERRIDE_DURATION seconds.

The controller runs as an async background task, processing the most recent
camera frame at ~2 Hz. Person detection uses YOLOv8n (ultralytics) running
in a thread-pool so the event loop is never blocked.
"""

import asyncio
import io
import logging
import time

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── Lazy-load YOLOv8n ──────────────────────────────────────────────────────────
_yolo_model = None          # None = not tried yet; False = failed to load


def _get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        try:
            from ultralytics import YOLO          # noqa: PLC0415
            _yolo_model = YOLO("yolov8n.pt")
            logger.info("[CamPan] YOLOv8n loaded successfully")
        except Exception as exc:
            logger.error("[CamPan] Could not load YOLOv8n – tracking disabled: %s", exc)
            _yolo_model = False
    return _yolo_model or None


# ── Controller ─────────────────────────────────────────────────────────────────
class CameraPanController:
    MODE_TRACKING         = "tracking"
    MODE_LOOK_AROUND      = "look_around"
    MODE_MANUAL_OVERRIDE  = "manual_override"

    # Tracking
    FRAME_EDGE_THRESHOLD  = 0.38   # fraction from each edge that triggers a pan
    PAN_STEP_TRACKING     = 12     # degrees per tracking correction
    PAN_COOLDOWN          = 1.3    # seconds between consecutive tracking pans

    # Look-around sweep
    PAN_STEP_LOOK_AROUND  = 6      # degrees per sweep step
    LOOK_AROUND_LIMIT     = 90     # degrees from the starting position
    LOOK_AROUND_INTERVAL  = 1.5    # seconds between sweep steps

    # Mode timeouts
    NO_SUBJECT_TIMEOUT       = 3.0   # seconds before switching TRACKING → LOOK_AROUND
    MANUAL_OVERRIDE_DURATION = 30    # seconds before exiting MANUAL_OVERRIDE

    # Detection
    CONFIDENCE_THRESHOLD = 0.40    # minimum YOLO confidence to count a person

    def __init__(self, user_id, channel_layer):
        self.user_id       = user_id
        self.channel_layer = channel_layer

        # Mode state
        self.mode = self.MODE_TRACKING

        # Raw JPEG bytes of the most recent frame
        self._latest_frame: bytes | None = None
        self._frame_width: int  = 640    # updated on each decoded frame
        self._frame_height: int = 480

        # Tracking bookkeeping
        self._last_detection_time = time.time()
        self._last_pan_time       = 0.0

        # Look-around state
        self._look_around_direction   = 1   # +1 = pan left, -1 = pan right
        self._look_around_accumulated = 0   # net degrees swept since mode entry
        self._last_look_around_step   = 0.0

        # Manual-override state
        self._override_expires = 0.0

        # Async loop
        self._task: asyncio.Task | None = None
        self._running = False

    # ── Public API ──────────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._task = asyncio.create_task(self._control_loop())
        print(f"[CamPan] Controller started for user {self.user_id} | channel_layer={self.channel_layer is not None}", flush=True)
        logger.info("[CamPan] Controller started for user %s", self.user_id)

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("[CamPan] Controller stopped for user %s", self.user_id)

    def process_frame(self, jpeg_bytes: bytes):
        """Feed a new raw JPEG frame into the controller (non-blocking)."""
        self._latest_frame = jpeg_bytes

    def set_mode(self, mode: str):
        """Switch to a named mode. Resets relevant state."""
        if mode not in (
            self.MODE_TRACKING,
            self.MODE_LOOK_AROUND,
            self.MODE_MANUAL_OVERRIDE,
        ):
            logger.warning("[CamPan] Unknown mode requested: %s", mode)
            return
        if mode != self.mode:
            logger.info("[CamPan] Mode: %s → %s", self.mode, mode)
        self.mode = mode
        if mode == self.MODE_LOOK_AROUND:
            self._look_around_accumulated = 0
            self._look_around_direction   = 1
            self._last_look_around_step   = 0.0
        elif mode == self.MODE_TRACKING:
            self._last_detection_time = time.time()

    def enter_manual_override(self, duration: float | None = None):
        """Enter MANUAL_OVERRIDE for *duration* seconds (default 30)."""
        secs = duration or self.MANUAL_OVERRIDE_DURATION
        self.mode = self.MODE_MANUAL_OVERRIDE
        self._override_expires = time.time() + secs
        logger.info("[CamPan] Manual override active for %.0fs", secs)

    # ── Async control loop ──────────────────────────────────────────────────────

    async def _control_loop(self):
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[CamPan] Control loop error: %s", exc, exc_info=True)
            await asyncio.sleep(0.5)   # 2 Hz

    async def _tick(self):
        now = time.time()

        # Manual override expiry check
        if self.mode == self.MODE_MANUAL_OVERRIDE and now > self._override_expires:
            print("[CamPan] Manual override expired → tracking", flush=True)
            self.set_mode(self.MODE_TRACKING)

        frame = self._latest_frame
        if frame is None:
            print("[CamPan] No frame received yet, waiting...", flush=True)
            return

        if self.mode == self.MODE_TRACKING:
            await self._tracking_tick(frame, now)
        elif self.mode == self.MODE_LOOK_AROUND:
            await self._look_around_tick(frame, now)
        # MANUAL_OVERRIDE: no autonomous panning; explicit commands only

    # ── Tracking mode ───────────────────────────────────────────────────────────

    async def _tracking_tick(self, frame: bytes, now: float):
        print(f"[CamPan] YOLO inference start...", flush=True)
        persons = await asyncio.to_thread(self._detect_persons, frame)
        print(f"[CamPan] YOLO done: {len(persons)} person(s) detected", flush=True)

        if not persons:
            elapsed = now - self._last_detection_time
            print(f"[CamPan] TRACKING: no person ({elapsed:.1f}s elapsed)", flush=True)
            if elapsed > self.NO_SUBJECT_TIMEOUT:
                print("[CamPan] No subject timeout → look_around", flush=True)
                self.set_mode(self.MODE_LOOK_AROUND)
            return

        self._last_detection_time = now

        w = self._frame_width
        frame_center = w / 2
        target = min(persons, key=lambda p: abs(p["cx"] - frame_center))
        left_thresh  = w * self.FRAME_EDGE_THRESHOLD
        right_thresh = w * (1.0 - self.FRAME_EDGE_THRESHOLD)

        print(f"[CamPan] target cx={target['cx']:.0f}, frame_w={w}, L={left_thresh:.0f}, R={right_thresh:.0f}, conf={target['conf']:.2f}", flush=True)

        if now - self._last_pan_time < self.PAN_COOLDOWN:
            print(f"[CamPan] pan cooldown active, skipping", flush=True)
            return

        if target["cx"] < left_thresh:
            print(f"[CamPan] → subject left, pan RIGHT -{self.PAN_STEP_TRACKING}°", flush=True)
            await self._send_pan(-self.PAN_STEP_TRACKING)
            self._last_pan_time = now
        elif target["cx"] > right_thresh:
            print(f"[CamPan] → subject right, pan LEFT +{self.PAN_STEP_TRACKING}°", flush=True)
            await self._send_pan(self.PAN_STEP_TRACKING)
            self._last_pan_time = now
        else:
            print(f"[CamPan] subject centred, no pan needed", flush=True)

    # ── Look-around mode ────────────────────────────────────────────────────────

    async def _look_around_tick(self, frame: bytes, now: float):
        persons = await asyncio.to_thread(self._detect_persons, frame)

        if persons:
            logger.info("[CamPan] Subject found during look-around → tracking")
            self.set_mode(self.MODE_TRACKING)
            return

        if now - self._last_look_around_step < self.LOOK_AROUND_INTERVAL:
            return   # not time for the next step yet

        self._last_look_around_step = now

        # Reverse direction at the sweep limits
        if self._look_around_accumulated >= self.LOOK_AROUND_LIMIT:
            self._look_around_direction = -1
        elif self._look_around_accumulated <= -self.LOOK_AROUND_LIMIT:
            self._look_around_direction = 1

        step = self._look_around_direction * self.PAN_STEP_LOOK_AROUND
        self._look_around_accumulated += step
        print(f"[CamPan] LOOK_AROUND: sending pan step={step:+d}°, accumulated={self._look_around_accumulated:+d}°", flush=True)
        await self._send_pan(step)

    # ── Person detection ────────────────────────────────────────────────────────

    def _detect_persons(self, jpeg_bytes: bytes) -> list[dict]:
        """
        Run YOLOv8n on *jpeg_bytes*.  Returns a list of dicts:
            {"cx": float, "cy": float,
             "x1": float, "y1": float, "x2": float, "y2": float,
             "conf": float}
        Returns [] if the model is unavailable or inference fails.
        """
        try:
            model = _get_yolo_model()
            if model is None:
                return []

            img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
            self._frame_width  = img.width
            self._frame_height = img.height
            img_array = np.array(img)

            results = model(img_array, classes=[0], verbose=False)   # class 0 = person

            persons = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                for box in boxes:
                    conf = float(box.conf[0])
                    if conf < self.CONFIDENCE_THRESHOLD:
                        continue
                    x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                    persons.append({
                        "cx":   (x1 + x2) / 2,
                        "cy":   (y1 + y2) / 2,
                        "x1":   x1, "y1": y1,
                        "x2":   x2, "y2": y2,
                        "conf": conf,
                    })

            return persons

        except Exception as exc:
            logger.error("[CamPan] Detection error: %s", exc)
            return []

    # ── Hardware communication ──────────────────────────────────────────────────

    async def _send_pan(self, delta: int):
        """Send a delta pan command to the hardware via Django Channels."""
        if not self.channel_layer or not self.user_id:
            print(f"[CamPan] _send_pan SKIPPED: channel_layer={self.channel_layer is not None}, user_id={self.user_id}", flush=True)
            return
        group_name = f"hardware_user_{self.user_id}"
        payload = {
            "type": "set_pan_position",
            "mode": "delta",
            "value": int(delta),
        }
        print(f"[CamPan] group_send → {group_name} | payload={payload}", flush=True)
        try:
            await self.channel_layer.group_send(
                group_name,
                {
                    "type": "device.command",
                    "payload": payload,
                },
            )
            print(f"[CamPan] group_send OK", flush=True)
        except Exception as exc:
            print(f"[CamPan] group_send FAILED: {exc}", flush=True)
            logger.error("[CamPan] Failed to send pan command: %s", exc)
