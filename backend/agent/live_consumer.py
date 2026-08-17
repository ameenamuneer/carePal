
import os
import re
import json
import time
import logging
import asyncio
import base64
from collections import deque
import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async

# App imports
from vitals.models import VitalReading, VitalType
from patients.models import PatientProfile
from medications.models import Medication, MedicationAdherence
from users.models import User
from agent.models import AgentSession, AgentMessage
from agent.energy_vad import EnergyEosDetector
from agent.elevenlabs_stt import transcribe_elevenlabs

logger = logging.getLogger(__name__)

# Configure the model
# Configure the model
MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

# ── Voice pipeline: mic → energy VAD → ElevenLabs STT → text injection ────────
#
# The microphone stream is NEVER forwarded to Gemini as audio. Instead:
#   1. The model finishes speaking → a listening window opens.
#   2. Incoming mic frames (PCM16 mono @ 16 kHz) are buffered while the window
#      is active and the AI is not speaking.
#   3. A wall-clock energy VAD (polled every VAD_TICK_MS) watches for speech
#      followed by a sustained silence run and fires end-of-speech.
#   4. The buffered utterance is transcribed by ElevenLabs Scribe.
#   5. The transcript is injected as TEXT with turn_complete=True; the model
#      replies. When it finishes, the window reopens.
#
# Gemini's own automatic activity detection is always DISABLED — turn
# boundaries are driven entirely by text injection.
INPUT_RATE = 16000

# Energy VAD tuning (see agent/energy_vad.py). Thresholds are RMS on 0..1.
# Thresholds are set high enough that the panning servo motors' mechanical noise
# does not register as speech. Because a higher threshold detects speech onset a
# little later (only once the talker is clearly above the noise floor), a rolling
# pre-roll buffer (below) prepends the audio leading up to the trigger so the
# quiet start of the utterance is never clipped.
VAD_TICK_MS = 100            # how often check_eos() is polled (wall clock)
VAD_ENERGY_THRESHOLD = 0.030  # frame RMS above this counts as speech
VAD_MIN_SPEECH_MS = 300      # min cumulative speech before EOS can fire
VAD_SILENCE_MS = 700         # trailing real-time silence that ends an utterance

# Rolling pre-roll: keep this much of the most recent mic audio at all times so
# that when a speech / barge-in trigger fires (possibly late, due to the raised
# threshold) we can prepend the lead-in and not miss the utterance onset.
VAD_PREROLL_MS = 1000

# Barge-in: while the AI is speaking we watch the mic with a SEPARATE, even less
# sensitive detector so the user can interrupt. The threshold is deliberately
# higher than the normal onset threshold so servo noise, faint background chatter
# or the echo of the AI's own voice cannot falsely interrupt; a longer sustained
# run is also required. Once confirmed we stop playback, tell Gemini to drop its
# turn, and start capturing the user's interrupting utterance (seeded from the
# pre-roll so its beginning is preserved).
VAD_BARGE_IN_ENERGY_THRESHOLD = 0.060  # higher than VAD_ENERGY_THRESHOLD (0.030)
VAD_BARGE_IN_MIN_SPEECH_MS = 400       # sustained loud speech needed to confirm

# ElevenLabs Scribe STT (see agent/elevenlabs_stt.py). Language auto-detected.
STT_MODEL_ID = "scribe_v2"
STT_TIMEOUT_MS = 20000

# When True, client camera frames ARE forwarded to the Gemini Live model so it
# can see (vision macro). Audio is never sent; only frames + injected text.
SEND_FRAMES_TO_GEMINI = False

# ── Edge-tracking (on-device detection) ───────────────────────────────────────
# When True, the native app runs on-device detection and streams normalized
# horizontal offsets ({"type":"track_offset"}). The backend converts those into
# proportional pan deltas and forwards them to the hardware group. No JPEG is
# needed for tracking on this path.
ENABLE_EDGE_TRACKING = True

# These are pushed to the client on connect as a {"type":"config"} message and
# initialize the client's two independent capture rates. "for now" they are
# module constants; move to Django settings / per-user config later.
LIVE_DETECTION_FPS   = 6     # on-device detection + offset send rate (Hz)
LIVE_GEMINI_FRAME_FPS = 0    # JPEG frames sent to Gemini for vision (0 = off)

# Proportional tracking params (backend-owned; adjustable live via _push_config).
# offset is the target's horizontal displacement from frame centre, normalized
# to [-1, 1] (negative = subject left of centre, positive = right).
TRACK_DEADZONE          = 0.12   # |offset| below this = centred, no pan
TRACK_PAN_GAIN          = 28.0   # degrees per unit offset (proportional Kp).
                                 # Kept below the ~30° half-FOV so each step
                                 # under-shoots and converges without oscillating.
TRACK_MIN_STEP          = 1      # smallest non-zero correction (degrees)
TRACK_MAX_STEP          = 25     # clamp on a single correction (degrees); stays
                                 # under half-FOV so no single step crosses centre
TRACK_COOLDOWN_MS       = 250    # min gap between consecutive pan commands
TRACK_MIN_CONF          = 0.50   # ignore detections below this confidence

class GeminiLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.input_queue = asyncio.Queue()
        self.stop_event = asyncio.Event()
        self.session = None

        # Get patient context
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            pass

        self.ai_is_speaking = False

        # ── Voice pipeline state ─────────────────────────────────────────────
        # Mic frames (int16 numpy arrays) buffered for the current utterance.
        self._mic_buf = []
        # Rolling pre-roll of the most recent mic frames (~VAD_PREROLL_MS), kept
        # updated on every frame so a late trigger can prepend the lead-in.
        self._preroll = deque()
        self._preroll_samples = 0
        self._preroll_max = int(INPUT_RATE * VAD_PREROLL_MS / 1000)
        # Energy VAD detector for the current listening window (None = closed).
        self._eos = None
        # Is a listening window currently open (model finished speaking)?
        self._window_active = False
        # Guard so only one transcription runs at a time.
        self._transcribing = False
        # Barge-in detector, active only while the AI is speaking (None = idle).
        self._barge_in = None
        # After a barge-in we discard the interrupted turn's trailing audio until
        # the next turn_complete / new injected turn takes over.
        self._suppress_ai_audio = False
        # ElevenLabs API key (resolved once; utterances skip STT if absent).
        self._elevenlabs_key = (
            os.environ.get("ELEVENLABS_API_KEY")
            or getattr(settings, "ELEVENLABS_API_KEY", "")
        )
        if not self._elevenlabs_key:
            logger.warning(
                "ELEVENLABS_API_KEY not set; live mic transcription will be skipped."
            )
        # Long-lived wall-clock VAD poller (started once, cancelled on disconnect).
        self._vad_ticker_task = asyncio.create_task(self._vad_ticker())

        # ── Edge-tracking state (on-device detection → proportional pan) ─────
        # Live-adjustable tracking params. Change these and call _push_config()
        # to retune the client's capture rates or the backend's pan math midcall.
        self._track_cfg = {
            "detection_fps":   LIVE_DETECTION_FPS,
            "gemini_frame_fps": LIVE_GEMINI_FRAME_FPS,
            "deadzone":        TRACK_DEADZONE,
            "pan_gain":        TRACK_PAN_GAIN,
            "min_step":        TRACK_MIN_STEP,
            "max_step":        TRACK_MAX_STEP,
            "cooldown_ms":     TRACK_COOLDOWN_MS,
            "min_conf":        TRACK_MIN_CONF,
        }
        self._last_edge_pan_ms = 0.0
        # Pushed to the client so it can initialize its two capture timers +
        # detection filtering. Only the subset the client needs is sent.
        await self._push_config()

        self.patient = await self._load_patient()
        self.task = asyncio.create_task(self.run_gemini_session())
        logger.info(f"Gemini Live WebSocket connected for user: {self.user}")

    @database_sync_to_async
    def get_patient_context(self):
        """
        Fetch patient details, recent vitals, and medications
        """
        try:
            # Assume the user IS the patient or related to one. 
            # Simplified: Get PatientProfile for current user
            if not self.user or not self.user.is_authenticated:
                return {
                    "name": "Guest",
                    "age": "Unknown",
                    "gender": "Unknown",
                    "vitals": "No recent records",
                    "medications": "Unknown"
                }

            patient = PatientProfile.objects.filter(user=self.user).first()
            if not patient:
                # Fallback: maybe user is a doctor/family? 
                # For demo/MVP, let's grab the first patient if none found for user (dangerous but useful for dev)
                # Or return generic
                return {
                    "name": self.user.get_full_name() or self.user.username,
                    "age": "Unknown",
                    "gender": "Unknown",
                    "vitals": "None",
                    "medications": "None"
                }

            # 1. Recent Vitals (Last 7 Days)
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_readings = VitalReading.objects.filter(
                patient=patient,
                measured_at__gte=seven_days_ago
            ).select_related('vital_type').order_by('-measured_at')[:10]
            
            vitals_summary = []
            for r in recent_readings:
                vitals_summary.append(f"- {r.vital_type.name}: {r.get_display_value()} ({r.measured_at.strftime('%Y-%m-%d %H:%M')})")
            
            vitals_str = "\n".join(vitals_summary) if vitals_summary else "No recent readings"

            # 2. Active Medications + today's adherence state (dynamic schedule)
            from datetime import date
            from medications.models import MedicationAdherence
            from medications.schedule_utils import get_schedule_for_date, get_times_for_frequency

            today = date.today()

            # Ensure adherence rows exist for today, then build a lookup
            # keyed by (medication_id, scheduled_time)
            adherence_today = MedicationAdherence.objects.filter(
                medication__patient=patient,
                scheduled_date=today,
            ).select_related('medication')
            adherence_map: dict = {}
            for a in adherence_today:
                adherence_map.setdefault(a.medication_id, []).append(a)

            active_meds = Medication.objects.filter(
                patient=patient,
                status='ACTIVE',
                start_date__lte=today,
            ).filter(
                __import__('django').db.models.Q(end_date__isnull=True) |
                __import__('django').db.models.Q(end_date__gte=today)
            )

            meds_summary = []
            for m in active_meds:
                times = get_times_for_frequency(m.frequency)
                if times:
                    times_str = ", ".join(f"{t.strftime('%H:%M')} ({label})" for t, label in times)
                else:
                    times_str = m.frequency

                records = adherence_map.get(m.id, [])
                if records:
                    statuses = []
                    for rec in sorted(records, key=lambda r: r.scheduled_time):
                        taken_time = (
                            f" — {rec.actual_datetime.strftime('%H:%M')}"
                            if rec.actual_datetime else ""
                        )
                        statuses.append(f"{rec.status}{taken_time}")
                    status_str = f" [TODAY: {' | '.join(statuses)}]"
                else:
                    status_str = " [TODAY: not yet recorded]"

                meds_summary.append(
                    f"- {m.medication_name} {m.dosage} @ {times_str}{status_str}"
                )

            meds_str = "\n".join(meds_summary) if meds_summary else "No active medications"

            return {
                "name": patient.user.get_full_name(),
                "age": str(patient.age) if hasattr(patient, 'age') else "Unknown",
                "gender": patient.gender if hasattr(patient, 'gender') else "Unknown",
                "vitals": vitals_str,
                "medications": meds_str
            }
        except Exception as e:
            logger.error(f"Error fetching context: {e}")
            return {
                "name": "Patient", 
                "age": "Unknown",
                "gender": "Unknown",
                "vitals": "Error fetching", 
                "medications": "Error fetching"
            }

    @database_sync_to_async
    def get_recent_messages_context(self):
        try:
            if not self.user or not self.user.is_authenticated:
                return "No previous conversation."
            
            patient = PatientProfile.objects.filter(user=self.user).first()
            if not patient:
                return "No previous conversation."
                
            session = AgentSession.objects.filter(patient=patient, status='ACTIVE', session_type='WEBSOCKET').first()
            if not session:
                session = AgentSession.objects.create(
                    patient=patient,
                    user=self.user,
                    session_type='WEBSOCKET',
                    status='ACTIVE'
                )
            self.db_session = session

            messages = AgentMessage.objects.filter(
                session__patient=patient
            ).order_by('-timestamp')[:30]
            
            messages = list(messages)[::-1]
            if not messages:
                return "No previous conversation."
                
            history = []
            for msg in messages:
                time_str = timezone.localtime(msg.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                history.append(f"[{time_str}] {msg.sender}: {msg.content}")
                
            return "\n".join(history)
        except Exception as e:
            logger.error(f"Error fetching recent messages: {e}")
            return "Error fetching conversation history."

    @database_sync_to_async
    def _load_patient(self):
        if not self.user or not self.user.is_authenticated:
            return None
        return PatientProfile.objects.filter(user=self.user).first()

    @database_sync_to_async
    def _get_pending_questions(self):
        from django.utils import timezone as tz
        from django.db import models as db_models
        from .models import PendingQuestion
        if not hasattr(self, 'patient') or not self.patient:
            return []
        now = tz.now()
        return list(
            PendingQuestion.objects.filter(
                patient=self.patient,
                asked=False,
            ).filter(
                db_models.Q(expires_at__isnull=True) | db_models.Q(expires_at__gt=now)
            ).order_by('priority', 'created_at')
        )

    @database_sync_to_async
    def _mark_questions_asked(self, question_ids):
        from django.utils import timezone as tz
        from .models import PendingQuestion
        PendingQuestion.objects.filter(id__in=question_ids).update(
            asked=True,
            asked_at=tz.now(),
        )

    @database_sync_to_async
    def save_turn_messages(self, user_text, ai_text):
        try:
            if not getattr(self, 'db_session', None):
                return
            if user_text:
                AgentMessage.objects.create(session=self.db_session, sender='USER', message_type='TEXT', content=user_text)
            if ai_text:
                AgentMessage.objects.create(session=self.db_session, sender='AGENT', message_type='TEXT', content=ai_text)
        except Exception as e:
            logger.error(f"Error saving messages: {e}")


    async def disconnect(self, close_code):
        self.stop_event.set()
        if getattr(self, '_vad_ticker_task', None):
            self._vad_ticker_task.cancel()
            try:
                await self._vad_ticker_task
            except asyncio.CancelledError:
                pass
        if hasattr(self, 'task'):
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Gemini Live WebSocket disconnected")

    # ── Voice pipeline: listening window, VAD ticker, transcribe + inject ─────

    def _push_preroll(self, frame):
        """Append a mic frame to the rolling pre-roll, trimming to VAD_PREROLL_MS."""
        self._preroll.append(frame)
        self._preroll_samples += frame.size
        while self._preroll_samples > self._preroll_max and len(self._preroll) > 1:
            old = self._preroll.popleft()
            self._preroll_samples -= old.size

    def _begin_window(self, seed_preroll=False):
        """
        Open a fresh listening window and start a new energy-VAD detector.

        When `seed_preroll` is True (barge-in), the current pre-roll is prepended
        to the utterance buffer and fed to the detector so the onset of speech
        that occurred before the trigger is not lost.
        """
        self._eos = EnergyEosDetector(
            rate=INPUT_RATE,
            energy_threshold=VAD_ENERGY_THRESHOLD,
            min_speech_ms=VAD_MIN_SPEECH_MS,
            silence_ms=VAD_SILENCE_MS,
        )
        if seed_preroll and self._preroll:
            self._mic_buf = list(self._preroll)
            for f in self._mic_buf:
                self._eos.push_audio(f)
        else:
            self._mic_buf = []
        self._window_active = True
        logger.info("Listening window OPEN (awaiting user speech).")

    def _close_window(self):
        """Close the listening window and drop any buffered mic audio."""
        self._window_active = False
        self._eos = None
        self._mic_buf = []

    def _start_barge_in_detector(self):
        """Arm a fresh, less-sensitive detector for the current AI turn."""
        self._barge_in = EnergyEosDetector(
            rate=INPUT_RATE,
            energy_threshold=VAD_BARGE_IN_ENERGY_THRESHOLD,
            min_speech_ms=VAD_BARGE_IN_MIN_SPEECH_MS,
            silence_ms=VAD_SILENCE_MS,  # unused here; we only read `saw_speech`
        )

    async def _handle_barge_in(self):
        """
        The user is talking over the AI. Stop the AI's playback, suppress the
        rest of its (now interrupted) turn, and open a listening window so the
        interrupting utterance is captured → transcribed → injected as a new
        turn (which also interrupts Gemini's generation server-side).
        """
        logger.info("🙋 Barge-in confirmed — interrupting AI playback.")
        self._barge_in = None
        self.ai_is_speaking = False
        self._suppress_ai_audio = True
        # Hard-stop AI audio on the client (frontend flushes its playback graph).
        try:
            await self.send(bytes_data=bytes([0x03]))
        except Exception as e:
            logger.error(f"Barge-in: failed to send interrupt to client: {e}")
        # Begin capturing the user's interrupting speech, seeded from the pre-roll
        # so the onset (which happened before the trigger fired) is preserved.
        self._begin_window(seed_preroll=True)

    async def _vad_ticker(self):
        """
        Long-lived wall-clock poller. Every VAD_TICK_MS it asks the current
        detector whether end-of-speech has been reached; if so it closes the
        window and kicks off transcription + injection.
        """
        try:
            while True:
                await asyncio.sleep(VAD_TICK_MS / 1000.0)
                if self.stop_event.is_set():
                    break
                if not self._window_active or self._eos is None:
                    continue
                if self.ai_is_speaking:
                    continue
                try:
                    if self._eos.check_eos():
                        # Capture and close before awaiting so new frames start a
                        # clean window on the next _begin_window().
                        saw_speech = self._eos.saw_speech
                        utterance = (
                            np.concatenate(self._mic_buf)
                            if self._mic_buf else np.array([], dtype=np.int16)
                        )
                        self._close_window()
                        if saw_speech and utterance.size > 0:
                            await self._transcribe_and_inject(utterance)
                        else:
                            # Nothing meaningful captured; reopen and keep listening.
                            self._begin_window()
                except Exception as e:
                    logger.error(f"VAD ticker error: {e}", exc_info=True)
        except asyncio.CancelledError:
            pass

    async def _transcribe_and_inject(self, utterance):
        """
        Transcribe a finished utterance with ElevenLabs Scribe and inject the
        text into Gemini Live as a completed user turn.
        """
        if self._transcribing:
            return
        self._transcribing = True
        try:
            if not self._elevenlabs_key:
                logger.warning("Skipping STT (no ELEVENLABS_API_KEY); reopening window.")
                self._begin_window()
                return

            try:
                text = await asyncio.to_thread(
                    transcribe_elevenlabs,
                    utterance,
                    INPUT_RATE,
                    STT_MODEL_ID,
                    STT_TIMEOUT_MS / 1000.0,
                    self._elevenlabs_key,
                )
            except Exception as e:
                logger.error(f"ElevenLabs STT failed: {e}")
                text = ""

            text = (text or "").strip()
            if not text:
                logger.info("Empty transcript; reopening listening window.")
                self._begin_window()
                return

            # Scribe annotates non-speech audio events in brackets, e.g.
            # "[Background noise]", "[clicking sound]". These are useful when they
            # accompany real speech, but a transcript containing ONLY such tags
            # means the user did not actually say anything — do not trigger a
            # response. Strip the tags; if nothing lexical remains, skip.
            lexical = re.sub(r'\[[^\]]*\]|\([^\)]*\)', '', text).strip()
            if not lexical:
                logger.info(f"Transcript is non-speech only ({text!r}); skipping injection.")
                self._begin_window()
                return

            logger.info(f"🗣️ Transcript injected: {text!r}")
            self.current_user_text = text
            # This new turn supersedes any interrupted AI turn: allow audio again.
            self._suppress_ai_audio = False
            # Inject as a completed user turn. The window reopens on turn_complete.
            await self.input_queue.put({"text": text})
        finally:
            self._transcribing = False

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive message from WebSocket (Client)
        Binary Protocol First Byte:
        0x00: Audio (PCM 16-bit)
        0x01: Image (JPEG)
        0x02: JSON Control
        0x03: Interrupt (not usually received from client, but available)
        """
        try:
            if bytes_data:
                msg_type_byte = bytes_data[0]
                payload_data = bytes_data[1:]

                if msg_type_byte == 0x00:
                    # Mic PCM16 frame. This audio is NEVER sent to Gemini.
                    if len(payload_data) < 2:
                        return
                    frame = np.frombuffer(payload_data, dtype=np.int16)
                    if frame.size == 0:
                        return

                    # Always keep the rolling pre-roll up to date (used to recover
                    # the onset when a trigger fires late).
                    self._push_preroll(frame)

                    # While the AI is speaking, watch for a barge-in with the
                    # less-sensitive detector; everything else is ignored.
                    if self.ai_is_speaking:
                        if self._barge_in is not None:
                            self._barge_in.push_audio(frame)
                            if self._barge_in.saw_speech:
                                await self._handle_barge_in()
                        return

                    # Normal listening: buffer the utterance and feed the energy
                    # VAD while a window is open (half-duplex).
                    if not self._window_active or self._eos is None:
                        return
                    self._mic_buf.append(frame)
                    self._eos.push_audio(frame)
                    return

                elif msg_type_byte == 0x01:
                    b64_image = base64.b64encode(payload_data).decode('utf-8')
                    # Store latest frame for manual-override inference
                    self.latest_frame_b64 = b64_image
                    if SEND_FRAMES_TO_GEMINI:
                        await self.input_queue.put({
                            "mime_type": "image/jpeg",
                            "data": b64_image
                        })
                
                elif msg_type_byte == 0x02:
                    data = json.loads(payload_data.decode('utf-8'))
                    if data.get("type") == "text":
                        await self.input_queue.put({"text": data.get("content") or data.get("data")})
                    elif data.get("type") == "track_offset":
                        await self._handle_track_offset(data)
                
                return

            if text_data:
                # Fallback for old text protocol
                data = json.loads(text_data)
                msg_type = data.get("type")
                if msg_type in ["audio", "image"]:
                    payload = {
                        "mime_type": data.get("mime_type"),
                        "data": data.get("data")
                    }
                    await self.input_queue.put(payload)
                elif msg_type == "text":
                    await self.input_queue.put({"text": data.get("data")})

        except Exception as e:
            logger.error(f"Error receiving data: {e}", exc_info=True)

    @database_sync_to_async
    def save_vital_reading(self, vital_type_str, value, systolic=None, diastolic=None):
        """
        Save a vital reading to the database
        """
        try:
            if not self.user or not self.user.is_authenticated:
                return {"success": False, "error": "No authenticated user context"}

            patient = PatientProfile.objects.filter(user=self.user).first()
            if not patient:
                return {"success": False, "error": "No patient profile found"}

            # Find vital type (case insensitive search)
            vital_type = VitalType.objects.filter(name__iexact=vital_type_str).first()
            if not vital_type:
                # Try by code
                vital_type = VitalType.objects.filter(code__iexact=vital_type_str).first()
            
            if not vital_type:
                return {"success": False, "error": f"Unknown vital type: {vital_type_str}"}

            # Create reading
            reading = VitalReading(
                patient=patient,
                vital_type=vital_type,
                measured_at=timezone.now(),
                unit=vital_type.unit,
                data_source=None, # Manually recorded via AI
                notes="Recorded via CarePAL AI Assistant"
            )

            if systolic is not None and diastolic is not None:
                reading.values = {"systolic": systolic, "diastolic": diastolic}
                reading.value = systolic # Primary value for basic queries
            else:
                reading.value = value

            reading.save()
            return {"success": True, "message": f"Saved {vital_type.name} reading: {reading.get_display_value()}"}

        except Exception as e:
            logger.error(f"Error saving vital: {e}")
            return {"success": False, "error": str(e)}

    async def run_gemini_session(self):
        api_key = os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None)
        
        if not api_key:
            logger.error("No Google API Key found")
            await self.send(text_data=json.dumps({"error": "No API Key"}))
            return

        # 1. Fetch Patient Context
        context = await self.get_patient_context()
        recent_messages_str = await self.get_recent_messages_context()
        
        # 2. Build System Instruction
        system_instruction = f"""You are CarePAL, a compassionate AI healthcare assistant for home-bound patients.

Context:
- Patient Name: {context['name']}
- Age: {context['age']}
- Gender: {context['gender']}

Recent Vitals (Last 7 Days):
{context['vitals']}

Active Medications:
{context['medications']}

Your Capabilities:
1. You have access to a motorised camera that tracks the patient automatically. The camera runs an on-device computer-vision model (YOLOv8n) and has three modes:
   • tracking (default) – automatically detects and follows the person nearest the frame centre. If no one is detected for a few seconds it switches to "look_around" automatically.
   • look_around – slowly sweeps left and right until a person is found, then returns to "tracking".
   • manual_override – you send a plain-English instruction; an orchestrator model interprets it and either switches mode or pans to a specific direction. After 30 seconds the camera reverts to tracking.

2. Camera Manual Override – how it works:
   Call the 'adjust_camera' tool with a plain-English textual command any time you need to intervene in camera positioning. A larger orchestrator model reads your command together with the current camera image and decides the best action. You do NOT need to specify degrees or JSON – just describe what you want. After 30 seconds the camera automatically returns to face/body tracking mode.

   Example commands you can pass:
   - "Look around to find the patient" → switches to look_around sweep mode
   - "Patient is not visible, search for them" → switches to look_around
   - "Switch to face tracking" → switches back to tracking mode
   - "Pan left, the patient moved to the left" → pans left by a suitable amount
   - "Turn right slightly" → pans right
   - "Track the person on the left side of the frame" → pans to bring them to centre

3. You can record vital signs if the patient shows you a device or tells you a reading. Pan to get a better view of the device if needed.

Rules:
- Speak clearly and warmly.
- The camera tracks the patient automatically. Only call 'adjust_camera' when the automated tracking is not keeping up, or when you specifically want to look somewhere.
- Do NOT call 'adjust_camera' repeatedly for small adjustments – trust the autonomous tracking.
- If you see a medical device, ask if you should record the reading.
- If the patient seems distressed, offer to call for help (simulated).
- Use the 'record_vital_reading' tool to save health data.
- Considering that the user is in GMT +5:30, check if there are any medications to be taken and whether the last dose was taken when you have a free moment in the conversation.

Activity Logging (IMPORTANT):
- You MUST silently call 'log_patient_activity' whenever you observe ANY of the following during conversation — without prompting the patient and without mentioning that you are logging:
  • Patient mentions eating a meal, snack, or any food/drink with calories (activity_type: MEAL)
  • Patient mentions any physical activity or confirms they did/skipped exercise (activity_type: EXERCISE)
  • Patient reports a symptom — pain, dizziness, nausea, shortness of breath, fatigue, etc. (activity_type: SYMPTOM)
  • Patient mentions how they slept (activity_type: SLEEP)
  • Patient mentions taking or skipping a medication (activity_type: MEDICATION)
  • Patient expresses an emotional state — anxious, happy, low, stressed (activity_type: MOOD)
  • You visually observe something significant via the camera (activity_type: VITAL_OBSERVATION or BEHAVIOR)
  • Any notable deviation from the patient's known routine (set is_notable: true and explain in notable_reason)
- Write the description in third-person past tense as a clinical log entry: "Patient had lunch at 2:30 pm."
- Include the actual time in observed_at if the patient mentions it.
- Do NOT skip logging because the observation seems minor — caregivers and clinicians rely on this log.

Medication Check-ins:
- Each medication in the Active Medications list has a [TODAY: ...] tag showing its adherence state for today.
- Only ask about medications marked [TODAY: not yet recorded]. Never ask about one already marked [TODAY: TAKEN] or [TODAY: SKIPPED] — it has already been confirmed.
- Ask naturally based on the time of day and the medication's scheduled time (shown next to each medication). Do not ask about an evening medication at 8am.
- When the patient says anything about medications — taken, skipped, unsure, side effects, or mentions a medication by name — immediately call log_patient_activity with activity_type='MEDICATION'. Capture exactly what they said in the description field.
- Do not attempt to interpret or judge adherence yourself. Just log faithfully.
- Do not ask about the same medication more than once per session.

Medication Timing Preferences:
- If the patient expresses a desire to permanently change WHEN they take a medication (e.g. "I'd like to take my morning pill at 7am from now on", "Can we move my evening dose to 9pm?"), acknowledge it warmly and log it immediately with activity_type='MEDICATION'. Include their exact preference in the description, e.g. "Patient requested to change Meftal Forte morning dose from 08:00 to 07:00 permanently."
- The backend Medication Monitor Agent will process this log and update the schedule automatically.
- Do NOT tell the patient you are logging it or that a backend agent will process it. Just say something like "I've noted that — your schedule will be updated."

Meal Logging:
- When the patient mentions eating anything — a meal, snack, drink with calories, or any food — immediately call log_patient_activity with activity_type='MEAL'.
- Capture exactly what they said in the description field with as much detail as possible: food names, quantities, cooking method, timing. Richer descriptions allow better calorie estimation.
- Do NOT attempt to count or estimate calories yourself — just describe faithfully.
- If the patient mentions how their appetite was, include appetite in details: {{"appetite": "GOOD"}} / {{"appetite": "POOR"}} / {{"appetite": "NORMAL"}}.
- Do not ask about meals more than once per meal window (morning / afternoon / evening).
- Do not tell the patient you are logging their meal.

Recent conversation history:
{recent_messages_str}
"""

        # Inject any pending questions from backend agents
        pending = await self._get_pending_questions()
        if pending:
            question_block = "\n\nPENDING FOLLOW-UP QUESTIONS (ask these naturally early in the session):\n"
            for pq in pending:
                question_block += f"- {pq.question}"
                if pq.context:
                    question_block += f"  [Context for you only: {pq.context}]"
                question_block += "\n"
            system_instruction += question_block
            await self._mark_questions_asked([pq.id for pq in pending])

        # 3. Define Tools
        # Google GenAI SDK v1Beta/v2 format for tool definitions using types
        tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="adjust_camera",
                        description="Adjust the camera pan/position based on a textual command.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "command": types.Schema(
                                    type="STRING",
                                    description="The textual command describing what action to take with the camera (e.g. 'Patient not visible', 'Pan left', 'User not centered')."
                                )
                            },
                            required=["command"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="record_vital_reading",
                        description="Record a patient's vital sign reading into the database.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "vital_type": types.Schema(
                                    type="STRING",
                                    description="Type of vital (e.g., 'Blood Pressure', 'Heart Rate', 'SpO2', 'Glucose', 'Temperature', 'Weight')"
                                ),
                                "value": types.Schema(
                                    type="NUMBER",
                                    description="Single value reading (for HR, SpO2, Temp, etc.)"
                                ),
                                "systolic": types.Schema(
                                    type="NUMBER",
                                    description="Systolic Blood Pressure"
                                ),
                                "diastolic": types.Schema(
                                    type="NUMBER",
                                    description="Diastolic Blood Pressure"
                                )
                            },
                            required=["vital_type"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="log_patient_activity",
                        description=(
                            "Silently log any patient activity, behaviour, or health observation "
                            "noticed during natural conversation. Use proactively — without being asked — "
                            "whenever you observe: meals eaten, exercise done or skipped, symptoms "
                            "reported, mood changes, sleep comments, medication remarks, or any "
                            "pattern that deviates from the patient's usual routine. "
                            "Call this in the background; do not interrupt the conversation flow."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "activity_type": types.Schema(
                                    type="STRING",
                                    description="Category: MEAL | EXERCISE | SLEEP | SYMPTOM | MEDICATION | MOOD | VITAL_OBSERVATION | BEHAVIOR | SOCIAL | ENVIRONMENT | OTHER"
                                ),
                                "description": types.Schema(
                                    type="STRING",
                                    description="Clear natural-language log entry, e.g. 'Patient had lunch at 2:30 pm', 'Reported dizziness when standing up'."
                                ),
                                "details": types.Schema(
                                    type="OBJECT",
                                    description="Structured extras. MEAL→{appetite:'GOOD|NORMAL|POOR'}. Do NOT include estimated_kcal or meal_items for MEAL — the monitor agent handles calorie estimation from the description. SYMPTOM→{symptom_name,severity,duration,body_part}. EXERCISE→{activity_name,duration_minutes,intensity}. SLEEP→{hours_slept,quality}. MOOD→{mood_description,energy_level}."
                                ),
                                "observed_at": types.Schema(
                                    type="STRING",
                                    description="ISO-8601 datetime when the activity occurred if patient mentioned a specific time. Omit to default to now."
                                ),
                                "is_notable": types.Schema(
                                    type="BOOLEAN",
                                    description="True if this deviates from the patient's usual pattern or warrants caregiver attention."
                                ),
                                "notable_reason": types.Schema(
                                    type="STRING",
                                    description="Why it is notable (only when is_notable is true)."
                                ),
                                "tags": types.Schema(
                                    type="ARRAY",
                                    items=types.Schema(type="STRING"),
                                    description="Short keyword tags, e.g. ['dizziness','skipped_walk']."
                                ),
                                "ai_confidence": types.Schema(
                                    type="STRING",
                                    description="Confidence in this observation: HIGH | MEDIUM | LOW"
                                )
                            },
                            required=["activity_type", "description"]
                        )
                    ),
                ]
            )
        ]

        client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=api_key,
        )

        # No microphone audio is ever sent to Gemini — turn boundaries are driven
        # entirely by injected text — so Gemini's own automatic activity detection
        # must be disabled.
        realtime_input_config = types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
        )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            media_resolution="MEDIA_RESOLUTION_MEDIUM",
            system_instruction=types.Content(parts=[types.Part(text=system_instruction)]),
            tools=tools, # Pass tool definitions
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
            realtime_input_config=realtime_input_config,
        )

        while not self.stop_event.is_set():
            try:
                async with client.aio.live.connect(model=MODEL, config=config) as session:
                    self.session = session
                    self.current_user_text = ""
                    self.current_ai_text = ""
                    # Fresh connection: open a listening window immediately so the
                    # user can speak first (no audio is ever sent to the model, so
                    # it will not greet unprompted). The window is recreated on
                    # every turn_complete thereafter.
                    self.ai_is_speaking = False
                    self._barge_in = None
                    self._suppress_ai_audio = False
                    self._begin_window()
                    logger.info("Connected to Gemini Live")
                    
                    # Start the sender loop
                    sender_task = asyncio.create_task(self.sender_loop())

                    # Receiver loop
                    logger.info("Starting receiver loop")
                    try:
                        while not self.stop_event.is_set():
                            async for response in session.receive():
                                if self.stop_event.is_set():
                                    break
                                
                                # 1. Handle actual media/text content first
                                if response.data:
                                    # After a barge-in, discard the interrupted
                                    # turn's trailing audio instead of replaying it.
                                    if not self._suppress_ai_audio:
                                        if not self.ai_is_speaking:
                                            # Transition into AI speech: arm a fresh
                                            # barge-in detector for this turn.
                                            self.ai_is_speaking = True
                                            self._start_barge_in_detector()
                                        payload = bytes([0x00]) + response.data
                                        await self.send(bytes_data=payload)

                                if response.text:
                                    logger.info(f"[AI_SPEAKING={self.ai_is_speaking}] Received text: {response.text[:50]}...")
                                    self.current_ai_text += response.text
                                    payload = bytes([0x02]) + json.dumps({
                                        "type": "text",
                                        "content": response.text
                                    }).encode('utf-8')
                                    await self.send(bytes_data=payload)
                                    
                                # 2. Handle Server Signals (turn_complete MUST override audio chunks in the same payload)
                                server_content = getattr(response, "server_content", None)
                                if server_content:
                                    if getattr(server_content, 'interrupted', False):
                                        logger.info(f"[AI_SPEAKING={self.ai_is_speaking}] Gemini signaled interrupt. Sending 0x03 to frontend.")
                                        await self.send(bytes_data=bytes([0x03]))
                                        self.ai_is_speaking = False
                                        self._barge_in = None

                                    if getattr(server_content, 'turn_complete', False):
                                        logger.info(f"[AI_SPEAKING={self.ai_is_speaking}] Server content: turn_complete=True. Resetting flag.")
                                        self.ai_is_speaking = False
                                        self._barge_in = None
                                        # Any barge-in suppression is stale once a
                                        # turn ends; let subsequent audio play.
                                        self._suppress_ai_audio = False

                                        user_t = self.current_user_text.strip()
                                        ai_t = self.current_ai_text.strip()
                                        if user_t or ai_t:
                                            asyncio.create_task(self.save_turn_messages(user_t, ai_t))

                                        self.current_user_text = ""
                                        self.current_ai_text = ""

                                        # Model finished speaking → open a listening
                                        # window, unless a barge-in already opened one
                                        # that is still capturing the user's speech.
                                        if not self._window_active:
                                            self._begin_window()
                                        
                                # 3. Handle Tool Calls directly on response OR inside model_turn
                                function_calls = []
                                tool_call = getattr(response, "tool_call", None)
                                if tool_call and hasattr(tool_call, "function_calls"):
                                    function_calls.extend(tool_call.function_calls)
                                
                                if server_content and getattr(server_content, 'model_turn', None):
                                    mt = server_content.model_turn
                                    if hasattr(mt, 'parts'):
                                        for part in mt.parts:
                                            if hasattr(part, 'function_call') and part.function_call:
                                                function_calls.append(part.function_call)
                                
                                for fc in function_calls:
                                    logger.info(f"Function call requested: {fc.name}")
                                    fc_args = dict(fc.args) if hasattr(fc, "args") and fc.args else {}
                                    fc_id = getattr(fc, 'id', None)
                                    if fc.name == "adjust_camera":
                                        command = fc_args.get("command", "")
                                        asyncio.create_task(self.handle_adjust_camera(command, fc_id))
                                    elif fc.name == "record_vital_reading":
                                        asyncio.create_task(self.handle_record_vital(fc_args, fc_id))
                                    elif fc.name == "log_patient_activity":
                                        asyncio.create_task(self.handle_log_activity(fc_args, fc_id))
                                            
                            logger.info("Receiver loop finished (turn complete). Re-entering...")
                            if self.stop_event.is_set():
                                break
                            
                            # Small delay to prevent busy looping if connection is dead but not raising error
                            await asyncio.sleep(0.05)

                    except Exception as inner_e:
                        logger.error(f"Error inside receiver loop: {inner_e}", exc_info=True)
                        
                    sender_task.cancel()
                    try:
                        await sender_task
                    except asyncio.CancelledError:
                        pass
                    
                if self.stop_event.is_set():
                    break
                    
                logger.warning("Gemini session disconnected silently, reconnecting in 1s...")
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("Gemini session cancelled")
                break
            except Exception as e:
                logger.error(f"Gemini session error: {e}", exc_info=True)
                if self.stop_event.is_set():
                    break
                logger.warning("Gemini session crashed, reconnecting in 2s...")
                await asyncio.sleep(2)
        
        logger.info("Exiting run_gemini_session")

    @database_sync_to_async
    def _save_activity_log(self, params: dict) -> dict:
        """Persist a PatientActivityLog entry with a current vitals snapshot."""
        from .models import PatientActivityLog
        from vitals.models import VitalReading

        try:
            if not self.user or not self.user.is_authenticated:
                return {"success": False, "error": "No authenticated user context"}

            patient = PatientProfile.objects.filter(user=self.user).first()
            if not patient:
                return {"success": False, "error": "No patient profile found"}

            # Resolve observed_at
            observed_at_raw = params.get('observed_at')
            if observed_at_raw:
                try:
                    from dateutil import parser as dateutil_parser
                    observed_at = dateutil_parser.parse(observed_at_raw)
                    if timezone.is_naive(observed_at):
                        observed_at = timezone.make_aware(observed_at)
                except Exception:
                    observed_at = timezone.now()
            else:
                observed_at = timezone.now()

            # Vitals snapshot — latest reading per type
            vitals_snapshot = {}
            try:
                seen = set()
                for r in (
                    VitalReading.objects
                    .filter(patient=patient, is_deleted=False)
                    .select_related('vital_type')
                    .order_by('-measured_at')
                ):
                    code = r.vital_type.code
                    if code not in seen:
                        seen.add(code)
                        vitals_snapshot[code] = {
                            'display': r.get_display_value(),
                            'measured_at': r.measured_at.isoformat(),
                            'unit': r.vital_type.unit,
                        }
                    if len(seen) >= 10:
                        break
            except Exception as ve:
                logger.warning(f"Could not snapshot vitals for activity log: {ve}")

            # Attach session if available
            session = getattr(self, 'db_session', None)

            log_entry = PatientActivityLog.objects.create(
                patient=patient,
                session=session,
                activity_type=params.get('activity_type', 'OTHER'),
                description=params.get('description', ''),
                details=params.get('details') or {},
                observed_at=observed_at,
                vitals_snapshot=vitals_snapshot,
                ai_confidence=params.get('ai_confidence', 'MEDIUM'),
                is_notable=bool(params.get('is_notable', False)),
                notable_reason=params.get('notable_reason', ''),
                tags=params.get('tags') or [],
            )
            logger.info(f"PatientActivityLog created: id={log_entry.id} type={log_entry.activity_type}")
            return {"success": True, "log_id": log_entry.id}

        except Exception as e:
            logger.error(f"Error saving activity log: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def handle_record_vital(self, args: dict, fc_id):
        """Handle record_vital_reading tool call."""
        result = await self.save_vital_reading(
            vital_type_str=args.get('vital_type', ''),
            value=args.get('value'),
            systolic=args.get('systolic'),
            diastolic=args.get('diastolic'),
        )
        if fc_id and self.session:
            try:
                await self.session.send_tool_response(
                    function_responses=[
                        types.FunctionResponse(
                            id=fc_id,
                            name="record_vital_reading",
                            response=result,
                        )
                    ]
                )
            except Exception as exc:
                logger.error(f"[record_vital] Failed to send tool response: {exc}")

    async def handle_log_activity(self, args: dict, fc_id):
        """Handle log_patient_activity tool call — silent background logging."""
        result = await self._save_activity_log(args)
        if fc_id and self.session:
            try:
                await self.session.send_tool_response(
                    function_responses=[
                        types.FunctionResponse(
                            id=fc_id,
                            name="log_patient_activity",
                            response=result,
                        )
                    ]
                )
            except Exception as exc:
                logger.error(f"[log_activity] Failed to send tool response: {exc}")

    async def sender_loop(self):
        logger.info("Starting sender loop")
        try:
            while True:
                item = await self.input_queue.get()

                if "text" in item:
                    # Injected transcript (or client text) → drives the model's turn.
                    logger.info(f"Sending text to Gemini: {item['text']}")
                    await self.session.send(input=item["text"], end_of_turn=True)
                else:
                    # It's media (image) dict {"mime_type":..., "data":...}
                    # Send dict with Base64 exactly as the SDK expects for LiveConnect!
                    await self.session.send(input=item)
                    
        except asyncio.CancelledError:
            logger.info("Sender loop cancelled")
            pass
        except Exception as e:
            logger.error(f"Error in sender loop: {e}", exc_info=True)

    async def _push_config(self):
        """Send current capture/tracking config to the client as a 0x02 JSON message.

        Called on connect and any time params change so the client can retune its
        two independent capture timers and detection filtering without a reconnect.
        """
        cfg = self._track_cfg
        msg = {
            "type": "config",
            "detection_fps":    cfg["detection_fps"],
            "gemini_frame_fps": cfg["gemini_frame_fps"],
            "min_conf":         cfg["min_conf"],
            "edge_tracking":    ENABLE_EDGE_TRACKING,
        }
        try:
            await self.send(bytes_data=b"\x02" + json.dumps(msg).encode("utf-8"))
            logger.info(f"[edge] pushed config → client: {msg}")
        except Exception as exc:
            logger.error(f"[edge] failed to push config: {exc}")

    async def _handle_track_offset(self, data: dict):
        """Convert an on-device detection offset into a proportional pan delta.

        Expects {"type":"track_offset", "dx": <float -1..1>, "conf": <float>,
        "found": <bool>}. dx < 0 → subject left of centre, dx > 0 → right.
        Sign convention matches the legacy YOLO controller (subject-left → negative
        delta). Corrections ramp proportionally from min_step at the edge of the
        deadzone up to max_step near the frame edge.
        """
        if not ENABLE_EDGE_TRACKING:
            return
        cfg = self._track_cfg
        now_ms = time.monotonic() * 1000.0

        if not bool(data.get("found", True)):
            return
        try:
            conf = float(data.get("conf", 1.0))
            dx = float(data.get("dx", 0.0))
        except (TypeError, ValueError):
            return
        if conf < cfg["min_conf"]:
            return

        dx = max(-1.0, min(1.0, dx))
        if abs(dx) < cfg["deadzone"]:
            return   # subject sufficiently centred

        if now_ms - self._last_edge_pan_ms < cfg["cooldown_ms"]:
            return   # respect inter-command cooldown

        over = abs(dx) - cfg["deadzone"]
        magnitude = cfg["pan_gain"] * over
        magnitude = max(cfg["min_step"], min(cfg["max_step"], magnitude))
        delta = int(round(magnitude)) * (1 if dx > 0 else -1)

        self._last_edge_pan_ms = now_ms
        await self._send_hardware_pan(delta)

    async def _send_hardware_pan(self, delta: int):
        """Send a raw delta pan command directly to the hardware channel group."""
        if not (hasattr(self, 'channel_layer') and self.channel_layer and self.user and self.user.id):
            logger.error("[pan] Missing channel_layer or user id – cannot dispatch command")
            return
        group_name = f"hardware_user_{self.user.id}"
        await self.channel_layer.group_send(
            group_name,
            {
                "type": "device.command",
                "payload": {
                    "type": "set_pan_position",
                    "mode": "delta",
                    "value": int(delta),
                },
            },
        )
        logger.info(f"[pan] Sent delta={delta} to {group_name}")

    async def handle_adjust_camera(self, command: str, fc_id):
        """
        Manual pan entry point called when the Live AI invokes 'adjust_camera'.

        Passes the command + current frame to an orchestrator model which returns
        a one-off pan delta. Autonomous subject tracking runs on the phone (edge
        ML Kit → track_offset); this tool is only for explicit manual pans.
        """
        logger.info(f"[adjust_camera] START | command='{command}' | fc_id={fc_id}")
        result_msg = "Command executed."

        try:
            api_key = os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None)
            client = genai.Client(
                api_key=api_key,
                http_options={"api_version": "v1beta"},
            )

            # System instruction embedded as first user turn to avoid SDK/API
            # version mismatches with the systemInstruction field.
            orchestrator_system = """You are the CarePal camera-control orchestrator.
The live AI assistant has sent a plain-English command about the camera.
Autonomous face/body tracking already runs continuously; your only job is to
translate an explicit manual-pan request into a one-off pan delta.

Given the command (and the current camera frame when available), return ONLY a
JSON object – no markdown, no extra text:

  {"action": "pan", "delta": <INT>}
    Positive delta = pan right. Negative delta = pan left. Range ±10 … ±60.
    Use delta 0 if no pan movement is required.

Decision guide:
  "turn left / pan left / move left [slightly/a lot]"      → pan -15 … -40
  "turn right / pan right / move right [slightly/a lot]"   → pan +15 … +40
  "track person on the left"                               → pan -20
  "track person on the right"                              → pan +20
  Ambiguous with frame available → inspect the frame and decide.

Respond with ONLY the JSON object, nothing else."""

            # Build contents: system prompt first, then optional image, then command
            if getattr(self, 'latest_frame_b64', None):
                image_bytes = base64.b64decode(self.latest_frame_b64)
                contents = [
                    types.Content(role="user", parts=[
                        types.Part(text=orchestrator_system),
                        types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                        types.Part(text=f"Command: {command}"),
                    ])
                ]
            else:
                contents = [
                    types.Content(role="user", parts=[
                        types.Part(text=orchestrator_system),
                        types.Part(text=f"Command: {command}"),
                    ])
                ]

            logger.info(f"[adjust_camera] Calling orchestrator model with command='{command}'")
            response = await asyncio.to_thread(
                client.models.generate_content,
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(temperature=0.1),
            )

            response_text = response.text.strip()
            # Strip any accidental markdown fences
            if response_text.startswith('```'):
                response_text = response_text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

            logger.info(f"[adjust_camera] Orchestrator response: {response_text}")
            action = json.loads(response_text)

            act = action.get('action')

            if act == 'pan':
                delta = int(action.get('delta', 0))
                if delta != 0:
                    await self._send_hardware_pan(delta)
                    result_msg = f"Panned camera by {delta}°."
                else:
                    result_msg = "No pan movement required."
                logger.info(f"[adjust_camera] Panned delta={delta}")

            else:
                logger.warning(f"[adjust_camera] Unknown orchestrator action: {act}")
                result_msg = "Orchestrator returned an unrecognised action."

        except Exception as exc:
            logger.error(f"[adjust_camera] Error: {exc}", exc_info=True)
            result_msg = f"Camera adjustment error: {exc}"

        finally:
            if fc_id and self.session:
                try:
                    await self.session.send_tool_response(
                        function_responses=[
                            types.FunctionResponse(
                                id=fc_id,
                                name="adjust_camera",
                                response={"result": result_msg},
                            )
                        ]
                    )
                    logger.info(f"[adjust_camera] Tool response sent: {result_msg}")
                except Exception as exc:
                    logger.error(f"[adjust_camera] Failed to send tool response: {exc}", exc_info=True)


