
import os
import re
import json
import time
import logging
import asyncio
import base64
import unicodedata
from collections import deque
import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
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

# Configure the model. Previously "models/gemini-2.5-flash-native-audio-preview-12-2025";
# 3.8 Live replies ~3x faster (0.6–1.7s vs 3–5s) and interrupts natively, for
# ~40% more per conversation (measured 2026-11-10).
MODEL = "models/gemini-3.8-live"

# How a barge-in interrupts the model's generation server-side. Measured:
#   • 2.5 native audio ignores a new client turn sent mid-generation (it keeps
#     talking) unless it is preceded by activity_start/activity_end, which yields
#     an immediate `interrupted`. The pair must be sent TOGETHER with the new text:
#     an empty activity_start/end makes 2.5 silently resume its previous reply.
#   • 3.x Live models interrupt on the client turn alone, and reject the
#     activity signals (1007 "Precondition check failed").
INTERRUPT_WITH_ACTIVITY_SIGNALS = "2.5" in MODEL

# Model output audio format (PCM16 mono), used to estimate client playback time.
OUTPUT_RATE = 24000

# ── Turn tracking ─────────────────────────────────────────────────────────────
# A turn opens when we send a message and closes when the model has finished
# replying. `turn_complete` alone is not a reliable close signal: after a tool
# call, Gemini often withholds it until the NEXT message is sent, where it then
# arrives (<2s after the send, before any new output) and belongs to the OLD
# turn. A turn_complete with no model activity since our send is therefore
# treated as stale and ignored. To never leave the user unable to speak, the VAD
# ticker also closes a turn when:
#   • generation_complete arrived, the server has been quiet for
#     TURN_GEN_DONE_GRACE_MS, and the client should have finished playing it;
#   • the model shows no activity at all for TURN_NO_RESPONSE_MS after a send
#     (handled like an empty turn → re-prompt once);
#   • the server goes quiet for TURN_STALL_MS mid-turn.
TURN_GEN_DONE_GRACE_MS = 1500
TURN_PLAYBACK_MARGIN_MS = 1000  # client-side buffering slack: the app's jitter buffer delays playback by 100–400 ms
TURN_NO_RESPONSE_MS    = 10000
TURN_STALL_MS          = 20000
# Tool calls: 3.x sends turn_complete right after a tool call, BEFORE we answer
# it, and then speaks its follow-up with no turn_complete at all; 2.5 calls tools
# mid-speech and may or may not say more afterwards. So a turn is never closed
# while a tool call is unanswered, nor until TURN_TOOL_FOLLOWUP_MS after the last
# tool response (time for the model to start its follow-up).
TURN_TOOL_FOLLOWUP_MS  = 3000
# After a barge-in, the old turn's trailing audio is suppressed until its
# `interrupted` / turn_complete arrives; give up waiting after this long.
BARGE_IN_SUPPRESS_MAX_MS = 3000

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

# Pauses mid-sentence: VAD_SILENCE_MS can end an utterance at a mere pause. So
# after each end-of-speech a new listening window opens at once ("continuation"
# window). If the patient goes on speaking before the AI's reply starts playing,
# that speech is transcribed and sent as a follow-up in the SAME turn (the model
# drops its pending reply and answers both). If the reply's audio arrives while
# the patient is still talking, it is held back; it is discarded if the patient
# really said more, and played if it was only noise. Holding never outlasts
# CONTINUATION_HOLD_MAX_S.
CONTINUATION_HOLD_MAX_S = 30

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

# Energy alone cannot separate servo motor noise from real speech, so a positive
# energy trigger during AI playback is only a CANDIDATE: we snapshot ~1s of audio
# (the pre-roll) and transcribe it with tag_audio_events=False. Only if real
# words come back do we actually interrupt. That verification transcript is used
# solely for the interrupt decision and is never sent to Gemini. The cooldown
# stops us from firing a fresh verification on every tick while one is pending or
# right after a rejected candidate.
VAD_BARGE_IN_COOLDOWN_MS = 1200

# ElevenLabs Scribe STT (see agent/elevenlabs_stt.py). Language is auto-detected
# but hinted with the language last spoken in the conversation (by either side),
# which mostly matters for short barge-in snippets.
STT_MODEL_ID = "scribe_v2"
STT_TIMEOUT_MS = 20000

# Known words ("keyterms", see agent/stt_keyterms.py) bias Scribe toward names,
# medicines and places, but make each transcription slower. Off for now.
STT_KEYTERMS_ENABLED = False

# Unicode script (prefix of each letter's unicodedata name) → ISO-639-3 hint.
# Malayalam, Tamil, Hindi and English each use a distinct script, so counting
# letters per script identifies the language of a transcript. Transcripts with
# no letters in these scripts (e.g. '我就是', 'أقول') are treated as noise.
STT_SCRIPT_LANGS = {
    "MALAYALAM": "mal",
    "LATIN": "eng",
    "TAMIL": "tam",
    "DEVANAGARI": "hin",
}
# Neighbouring scripts STT sometimes picks for Malayalam speech (e.g.
# 'ఏది model అనుకుంటున్నారు?'). Gemini can still read them, so such transcripts
# are passed through, but they never become the STT language hint.
STT_PASSTHROUGH_SCRIPTS = {"TELUGU", "KANNADA"}

# Barge-in echo filter: if at least this fraction of the words in a barge-in
# snippet appear in what the AI is currently saying, the mic most likely picked
# up the AI's own voice from the speaker, so the interrupt is rejected.
BARGE_IN_ECHO_OVERLAP = 0.6

# Sent to the model in place of a transcript that is mostly in scripts the
# patient doesn't speak, so it asks them to repeat rather than staying silent.
UNCLEAR_AUDIO_NOTICE = (
    "[UNCLEAR_AUDIO] The patient said something, but the speech could not be "
    "recognised. Briefly and kindly ask them to repeat it."
)

# Camera → Gemini. The app's camera button turns the live feed on/off: while on,
# the app sends JPEG frames at LIVE_GEMINI_FRAME_FPS and they are forwarded to
# Gemini as realtime video; while off, it sends none. Independently, the
# 'view_camera' tool asks the app for one fresh snapshot (works with the feed
# off) and waits up to CAMERA_SNAPSHOT_TIMEOUT_S for it.
CAMERA_SNAPSHOT_TIMEOUT_S = 5.0
# A frame younger than this counts as "current" for the adjust_camera orchestrator.
CAMERA_FRAME_FRESH_S = 2.0

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
LIVE_GEMINI_FRAME_FPS = 1    # JPEG frame rate while the app's camera feed is on

# Proportional tracking params (backend-owned; adjustable live via _push_config).
# offset is the target's horizontal displacement from frame centre, normalized
# to [-1, 1] (negative = subject left of centre, positive = right).
TRACK_DEADZONE          = 0.12   # |offset| below this = centred, no pan
TRACK_PAN_GAIN          = 8.5   # degrees per unit offset (proportional Kp)
TRACK_MIN_STEP          = 0.25      # smallest non-zero correction (degrees)
TRACK_MAX_STEP          = 35     # clamp on a single correction (degrees)
TRACK_COOLDOWN_MS       = 80    # min gap between consecutive pan commands
TRACK_MIN_CONF          = 0.50   # ignore detections below this confidence

# ── Object-loss coasting / search (dead-reckoning) ───────────────────────────
# When the subject suddenly disappears, extrapolate the direction it was moving
# from a short position history and pan that way to search for it, up to a bounded
# total travel before giving up. Driven by the found=false frames the phone keeps
# streaming at the detection rate — no separate timer.
TRACK_COAST_ENABLE      = True
TRACK_HISTORY_MS        = 500    # window of recent found samples kept for velocity
TRACK_COAST_MIN_VEL     = 0.6    # min |dx|/sec at loss to treat it as real motion;
                                 # below this = detection blip → hold, don't chase
TRACK_COAST_STEP        = 6      # degrees per search pan while coasting
TRACK_SEARCH_MAX_DEG    = 60     # cumulative search-travel cap before giving up
TRACK_COAST_TIMEOUT_MS  = 1500   # also give up if the subject stays lost this long

class GeminiLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # No valid login (e.g. expired token): refuse instead of running an
        # anonymous session with no patient context and no camera. The app
        # refreshes its token and reconnects on close code 4001.
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            logger.warning("Live AI connection without a valid login; closing (4001).")
            await self.accept()
            await self.close(code=4001)
            return
        await self.accept()
        # Start of this live session; the personal-notes update after it reads
        # the conversation from here on.
        self._connected_at = timezone.now()
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
        # True while a barge-in verification transcription is in flight, so the
        # ticker/receiver don't spawn a second one for the same noise burst.
        self._barge_in_checking = False
        # Mic frames from the moment a barge-in candidate fires (seeded with the
        # pre-roll) until STT verification decides. Verification takes 1–3s, far
        # longer than the 1s pre-roll, so without this the first words of an
        # interruption ("stop, …") were lost. None = no candidate pending.
        self._barge_capture = None
        # monotonic() timestamp before which no new barge-in verification fires
        # (set after a rejected candidate to avoid hammering STT on motor noise).
        self._barge_in_cooldown_until = 0.0
        # After a barge-in we discard the interrupted turn's trailing audio until
        # that turn's `interrupted` / turn_complete arrives (or it ends naturally).
        self._suppress_ai_audio = False
        # Set when a message is sent while the interrupted turn is still alive:
        # its `interrupted` / turn_complete is then expected and must not be
        # mistaken for the new turn's. Cleared on arrival or after a deadline.
        self._expect_stale_close = False
        self._expect_stale_close_until = 0.0
        # Empty-turn recovery: native-audio models occasionally close a turn
        # without emitting any audio/text/tool call (e.g. after a disfluent input
        # the model "thinks" and says nothing). _turn_saw_output flips True on any
        # real model output this turn; if a turn completes with none, we re-prompt
        # the last user text exactly once (_empty_turn_retried guards against loops).
        self._turn_saw_output = False
        self._last_injected_text = ""
        self._empty_turn_retried = False
        # Turn tracking (see TURN_* constants). _turn_activity: any model signal
        # (thought, audio, text, tool call, generation_complete) since our send.
        self._turn_open = False
        self._turn_activity = False
        self._turn_gen_done = False
        self._turn_sent_at = 0.0
        self._last_server_msg_at = 0.0
        # Audio actually forwarded to the client this turn, to estimate when the
        # client finishes playing it.
        self._turn_audio_started_at = None
        self._turn_audio_bytes = 0
        # Tool calls dispatched but not yet answered, and when the last answer
        # was sent (see TURN_TOOL_FOLLOWUP_MS).
        self._tools_outstanding = 0
        self._last_tool_response_at = 0.0
        # ISO-639-3 hint for STT: the language last spoken by either side.
        self._lang_hint = None
        # Known words for speech recognition (filled in connect()).
        self._stt_keyterms = []
        # Gemini Live session resumption handle (valid ~2h after a disconnect).
        self._resume_handle = None
        # Set by a go_away-triggered planned reconnect (skips the backoff sleep).
        self._planned_reconnect = False
        self._go_away_task = None
        # Continuation after a pause (see CONTINUATION_HOLD_MAX_S): is the open
        # listening window a continuation of a message already sent, and AI audio
        # held back while the patient was still talking.
        self._continuation = False
        self._holding_for_continuation = False
        self._hold_started_at = 0.0
        self._held_audio = []
        # Camera: is the app's live feed on (camera button)? Latest frame received
        # (for the adjust_camera orchestrator), and futures waiting for the next
        # frame after a snapshot request.
        self._camera_feed_on = False
        self.latest_frame_b64 = None
        self._latest_frame_at = 0.0
        self._frame_waiters = []
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
            "coast_enable":    TRACK_COAST_ENABLE,
            "history_ms":      TRACK_HISTORY_MS,
            "coast_min_vel":   TRACK_COAST_MIN_VEL,
            "coast_step":      TRACK_COAST_STEP,
            "search_max_deg":  TRACK_SEARCH_MAX_DEG,
            "coast_timeout_ms": TRACK_COAST_TIMEOUT_MS,
        }
        self._last_edge_pan_ms = 0.0
        # Object-loss coasting state. _track_hist holds recent (t_ms, dx) samples
        # from found detections; on a sudden loss we extrapolate a search direction.
        self._track_hist = deque()
        self._coasting = False        # currently searching for a lost subject
        self._coast_dir = 0           # +1 / -1 extrapolated search direction
        self._search_travel = 0.0     # cumulative degrees panned this search
        self._coast_start_ms = 0.0    # when the current search began
        # Pushed to the client so it can initialize its two capture timers +
        # detection filtering. Only the subset the client needs is sent.
        await self._push_config()

        self.patient = await self._load_patient()
        # Known words for STT, prepared in the background (one cached Gemini
        # call) so connecting is not delayed; transcription uses none until ready.
        if STT_KEYTERMS_ENABLED:
            self._keyterms_task = asyncio.create_task(self._prepare_stt_keyterms())
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

            # 1. Recent Vitals (Last 7 Days). Timestamps are stored as absolute
            # instants (UTC); localtime() renders them in settings.TIME_ZONE (IST)
            # regardless of the host/container clock.
            seven_days_ago = timezone.now() - timedelta(days=7)
            readings = VitalReading.objects.filter(
                patient=patient, is_deleted=False
            ).select_related('vital_type')
            recent_readings = readings.filter(
                measured_at__gte=seven_days_ago
            ).order_by('-measured_at')[:10]

            vitals_summary = []
            for r in recent_readings:
                vitals_summary.append(f"- {r.vital_type.name}: {r.get_display_value()} ({self._fmt_local(r.measured_at)})")

            # For vital types with nothing in the last 7 days, include the latest
            # older reading so the AI still knows the last known value.
            recent_type_ids = set(
                readings.filter(measured_at__gte=seven_days_ago)
                .values_list('vital_type_id', flat=True)
            )
            older_summary = []
            seen_types = set()
            for r in readings.filter(measured_at__lt=seven_days_ago).order_by('-measured_at'):
                if r.vital_type_id in recent_type_ids or r.vital_type_id in seen_types:
                    continue
                seen_types.add(r.vital_type_id)
                older_summary.append(
                    f"- {r.vital_type.name}: {r.get_display_value()} "
                    f"({self._fmt_local(r.measured_at)} — older than 7 days, last known value)"
                )

            vitals_str = "\n".join(vitals_summary) if vitals_summary else "No readings in the last 7 days"
            if older_summary:
                vitals_str += "\n" + "\n".join(older_summary)

            # 2. Active Medications + today's adherence state (dynamic schedule)
            from medications.models import MedicationAdherence
            from medications.schedule_utils import get_schedule_for_date, get_times_for_frequency

            # The patient's local date (IST), not the container's UTC date.
            today = timezone.localdate()

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
                            f" — {timezone.localtime(rec.actual_datetime).strftime('%H:%M')}"
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

            location = ", ".join(
                part for part in (patient.city, patient.state, patient.country) if part
            )

            def card(*parts):
                return "; ".join(f"{label}: {value}" for label, value in parts if value)

            doctor = card(
                ("Name", patient.doctor_name), ("Specialty", patient.doctor_specialty),
                ("Clinic", patient.doctor_clinic), ("Phone", patient.doctor_phone),
                ("Email", patient.doctor_email), ("Address", patient.doctor_address),
                ("Notes", patient.doctor_notes),
            )
            pharmacy = card(
                ("Name", patient.pharmacy_name), ("Phone", patient.pharmacy_phone),
                ("Address", patient.pharmacy_address), ("Notes", patient.pharmacy_notes),
            )
            return {
                "name": patient.user.get_full_name(),
                "location": location if patient.city else "",
                "personal_notes": patient.personal_notes.strip(),
                "doctor": doctor,
                "pharmacy": pharmacy,
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

    async def _prepare_stt_keyterms(self):
        """Known words for speech recognition, in every app script (see agent/stt_keyterms.py)."""
        from .stt_keyterms import build_keyterms, expand_scripts
        try:
            terms = await database_sync_to_async(build_keyterms)(self.patient)
            self._stt_keyterms = await asyncio.to_thread(expand_scripts, terms)
            logger.info(f"STT keyterms ready ({len(self._stt_keyterms)}): {self._stt_keyterms[:12]}")
        except Exception as e:
            logger.warning(f"Could not prepare STT keyterms: {e}")

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
        if not hasattr(self, 'stop_event'):
            return  # rejected in connect() before any setup
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
        # Persist the turn that was in flight (its turn never closed).
        user_t = (getattr(self, 'current_user_text', '') or '').strip()
        ai_t = (getattr(self, 'current_ai_text', '') or '').strip()
        if user_t or ai_t:
            await self.save_turn_messages(user_t, ai_t)
        # Fold this session into the patient's personal notes (Celery; the delay
        # lets any in-flight message saves land first).
        if getattr(self, 'patient', None) and getattr(self, '_connected_at', None):
            try:
                from .tasks import update_personal_notes
                await asyncio.to_thread(
                    update_personal_notes.apply_async,
                    args=[self.patient.id, self._connected_at.isoformat()],
                    countdown=10,
                )
            except Exception as e:
                logger.error(f"Could not queue personal notes update: {e}")
        logger.info("Gemini Live WebSocket disconnected")

    # ── Voice pipeline: listening window, VAD ticker, transcribe + inject ─────

    def _push_preroll(self, frame):
        """Append a mic frame to the rolling pre-roll, trimming to VAD_PREROLL_MS."""
        self._preroll.append(frame)
        self._preroll_samples += frame.size
        while self._preroll_samples > self._preroll_max and len(self._preroll) > 1:
            old = self._preroll.popleft()
            self._preroll_samples -= old.size

    def _begin_window(self, seed_frames=None):
        """
        Open a fresh listening window and start a new energy-VAD detector.

        `seed_frames` (barge-in) are mic frames already captured for this
        utterance — the pre-roll plus everything since the interrupt candidate
        fired — prepended to the buffer and fed to the detector so the start of
        the interrupting speech is not lost.
        """
        self._eos = EnergyEosDetector(
            rate=INPUT_RATE,
            energy_threshold=VAD_ENERGY_THRESHOLD,
            min_speech_ms=VAD_MIN_SPEECH_MS,
            silence_ms=VAD_SILENCE_MS,
        )
        if seed_frames:
            self._mic_buf = list(seed_frames)
            for f in self._mic_buf:
                self._eos.push_audio(f)
        else:
            self._mic_buf = []
        self._window_active = True
        logger.debug("Listening window OPEN (awaiting user speech).")

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
        # Begin capturing the user's interrupting speech, seeded with everything
        # captured since the candidate fired (incl. the pre-roll before it), so
        # the whole utterance from its onset is transcribed.
        seed = self._barge_capture if self._barge_capture else list(self._preroll)
        self._barge_capture = None
        self._begin_window(seed_frames=seed)

    # ── Local time ───────────────────────────────────────────────────────────
    # Datetimes are absolute instants; Django converts them to settings.TIME_ZONE
    # (Asia/Kolkata), so the result does not depend on the host/container clock.

    @staticmethod
    def _fmt_local(dt) -> str:
        return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M')

    @staticmethod
    def _now_str() -> str:
        return timezone.localtime().strftime('%A %d %B %Y, %I:%M %p IST')

    # ── Language hint + barge-in plausibility ────────────────────────────────

    @staticmethod
    def _script_lang(text: str):
        """
        Language of `text` from the script its letters are written in: the
        majority script among STT_SCRIPT_LANGS. Returns None when most letters
        are in other scripts (e.g. '我就是', 'أقول'), i.e. the transcript is not
        in a language the patient speaks; a few stray foreign characters do not
        count against an otherwise valid transcript. Code-switched Malayalam
        keeps English loanwords in Latin script, so the Malayalam majority wins.
        """
        counts = {}
        passthrough = 0
        foreign = 0
        for ch in text:
            if ch.isalpha():
                script = unicodedata.name(ch, "").split(" ", 1)[0]
                if script in STT_SCRIPT_LANGS:
                    counts[script] = counts.get(script, 0) + 1
                elif script in STT_PASSTHROUGH_SCRIPTS:
                    passthrough += 1
                else:
                    foreign += 1
        known = sum(counts.values()) + passthrough
        if not known or foreign > known:
            return None
        if not counts or passthrough > sum(counts.values()):
            return "pass"  # readable, but not a language to hint STT with
        return STT_SCRIPT_LANGS[max(counts, key=counts.get)]

    def _update_lang_hint(self, text: str):
        lang = self._script_lang(text)
        if lang and lang != "pass" and lang != self._lang_hint:
            logger.info(f"STT language hint → {lang}")
            self._lang_hint = lang

    def _is_echo_of_ai(self, text: str) -> bool:
        """True if most words of `text` occur in what the AI is saying this turn."""
        words = re.findall(r"\w+", text.lower())
        if not words:
            return False
        ai_words = set(re.findall(r"\w+", self.current_ai_text.lower()))
        overlap = sum(1 for w in words if w in ai_words) / len(words)
        return overlap >= BARGE_IN_ECHO_OVERLAP

    # ── Turn tracking ────────────────────────────────────────────────────────

    def _mark_turn_sent(self):
        """A message is being sent to Gemini: open a new turn."""
        now = time.monotonic()
        # If the interrupted turn is still alive, its interrupted/turn_complete
        # is still to come and must not close this new turn.
        if self._suppress_ai_audio:
            self._expect_stale_close = True
            self._expect_stale_close_until = now + BARGE_IN_SUPPRESS_MAX_MS / 1000.0
        self._turn_open = True
        self._turn_activity = False
        self._turn_gen_done = False
        self._turn_sent_at = now
        self._last_server_msg_at = now
        self._turn_audio_started_at = None
        self._turn_audio_bytes = 0

    def _open_implicit_turn(self):
        """Model output arrived with no turn open (e.g. 3.x speaks after a tool
        call whose turn already closed): track it as a turn of its own."""
        self._mark_turn_sent()
        self._turn_activity = True

    def _patient_continuing(self) -> bool:
        """The patient started speaking again in a continuation window."""
        return (
            self._continuation
            and self._window_active
            and self._eos is not None
            and self._eos.saw_speech
        )

    def _discard_held_audio(self):
        self._held_audio = []
        self._holding_for_continuation = False

    async def _release_held_audio(self):
        """The patient's extra speech was only noise: play the held reply."""
        if not self._holding_for_continuation:
            return
        chunks = self._held_audio
        self._discard_held_audio()
        if not chunks or self._suppress_ai_audio:
            return
        logger.info("Releasing held AI reply (no follow-up speech).")
        await self._start_ai_audio()
        for chunk in chunks:
            self._turn_audio_bytes += len(chunk)
            await self.send(bytes_data=bytes([0x00]) + chunk)

    async def _start_ai_audio(self):
        """Transition into AI speech: arm barge-in, stop continuation capture."""
        if self._continuation:
            self._continuation = False
            self._close_window()
        if not self.ai_is_speaking:
            self.ai_is_speaking = True
            self._start_barge_in_detector()
        if self._turn_audio_started_at is None:
            self._turn_audio_started_at = time.monotonic()

    def _end_stale_close(self):
        """The interrupted turn has closed: stop suppressing its audio."""
        self._expect_stale_close = False
        self._suppress_ai_audio = False

    async def _finish_turn(self, reason: str):
        """
        Close the current turn: re-prompt once if the model said nothing,
        otherwise persist the exchange and open a listening window.
        """
        self._turn_open = False
        self.ai_is_speaking = False
        self._barge_in = None
        self._continuation = False
        # Any barge-in suppression is stale once a turn ends; let subsequent
        # audio play.
        self._suppress_ai_audio = False
        if reason != "turn_complete":
            logger.info(f"Closing turn without turn_complete ({reason}).")

        if self.current_ai_text.strip():
            self._update_lang_hint(self.current_ai_text)

        # Empty-turn recovery: if the model closed the turn without any
        # audio/text/tool call, it silently ignored the user. Re-send the last
        # user text ONCE to elicit a real response.
        if (
            not self._turn_saw_output
            and self._last_injected_text
            and not self._empty_turn_retried
        ):
            self._empty_turn_retried = True
            logger.info(
                "Model returned an empty turn (no audio/text/tool call); "
                "re-prompting the last user message once."
            )
            # Don't save yet (no AI reply) and don't open a listening window —
            # re-drive the same turn. current_user_text is kept so it saves
            # after the retry completes.
            await self.input_queue.put({"text": self._last_injected_text})
            return

        if not self._turn_saw_output and self._empty_turn_retried:
            logger.info("Model returned an empty turn again after retry; giving up.")
        user_t = self.current_user_text.strip()
        ai_t = self.current_ai_text.strip()
        if user_t or ai_t:
            asyncio.create_task(self.save_turn_messages(user_t, ai_t))

        self.current_user_text = ""
        self.current_ai_text = ""
        self._last_injected_text = ""
        self._empty_turn_retried = False
        self._turn_saw_output = False

        # Model finished speaking → open a listening window, unless a barge-in
        # already opened one that is still capturing the user's speech. If an
        # interrupt candidate is still being verified, the user started talking
        # before the AI finished: keep that audio as the start of the utterance.
        if not self._window_active:
            seed = self._barge_capture
            self._barge_capture = None
            self._begin_window(seed_frames=seed)

    async def _turn_watchdog(self):
        """
        Polled by the VAD ticker. Guarantees an open turn always closes (so a
        listening window always reopens) even when Gemini never sends
        turn_complete for it.
        """
        now = time.monotonic()
        if self._expect_stale_close and now >= self._expect_stale_close_until:
            logger.info("Interrupted turn never closed; ending audio suppression.")
            self._end_stale_close()
        if self._holding_for_continuation:
            if now - self._hold_started_at > CONTINUATION_HOLD_MAX_S:
                logger.warning("Held AI reply for too long; releasing it.")
                await self._release_held_audio()
            return  # resolved by the continuation's transcription
        if not self._turn_open:
            return
        quiet = now - self._last_server_msg_at
        tools_settled = (
            self._tools_outstanding == 0
            and now - self._last_tool_response_at >= TURN_TOOL_FOLLOWUP_MS / 1000.0
        )
        if self._turn_gen_done and tools_settled:
            playback_end = 0.0
            if self._turn_audio_started_at is not None:
                playback_end = (
                    self._turn_audio_started_at
                    + self._turn_audio_bytes / (OUTPUT_RATE * 2)
                    + TURN_PLAYBACK_MARGIN_MS / 1000.0
                )
            if quiet >= TURN_GEN_DONE_GRACE_MS / 1000.0 and now >= playback_end:
                await self._finish_turn("generation complete")
        elif not self._turn_activity and now - self._turn_sent_at >= TURN_NO_RESPONSE_MS / 1000.0:
            await self._finish_turn("no response from model")
        elif quiet >= TURN_STALL_MS / 1000.0:
            await self._finish_turn("model went quiet mid-turn")

    @staticmethod
    def _is_transient_disconnect(exc: BaseException) -> bool:
        """
        True if the exception is an expected/handled Gemini Live socket drop
        (server-side 1011 internal error, idle close, network blip) rather than
        a real bug in our code. These are recoverable by reconnecting, so we log
        them as clean warnings instead of dumping a full traceback.
        """
        # SDK surfaces server closes as APIError with a WebSocket close code.
        if isinstance(exc, genai_errors.APIError):
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if code in (1011, 1006, 1001, 1000, 500, 503):
                return True
        name = type(exc).__name__
        if "ConnectionClosed" in name:
            return True
        # Fallback: match the close codes / phrasing in the message text.
        msg = str(exc)
        return any(
            tok in msg
            for tok in ("1011", "1006", "1001", "internal error", "Internal error")
        )

    def _rearm_barge_in(self):
        """Re-arm (or clear) the barge-in detector after a rejected candidate."""
        if self.ai_is_speaking:
            self._start_barge_in_detector()
        else:
            self._barge_in = None

    async def _verify_barge_in(self, audio: np.ndarray):
        """
        Confirm a candidate barge-in with STT before interrupting.

        `audio` is a ~1s snapshot of the most recent mic pre-roll captured when
        the energy detector tripped during AI playback. We transcribe it with
        tag_audio_events=False (so non-speech events don't produce bracket tags)
        and only trigger the interrupt if real words come back. This transcript
        is used solely for the interrupt decision — it is NEVER sent to Gemini.
        """
        try:
            if audio is None or audio.size == 0 or not self._elevenlabs_key:
                self._rearm_barge_in()
                return
            try:
                text = await asyncio.to_thread(
                    transcribe_elevenlabs,
                    audio,
                    INPUT_RATE,
                    STT_MODEL_ID,
                    STT_TIMEOUT_MS / 1000.0,
                    self._elevenlabs_key,
                    False,  # tag_audio_events — suppress non-speech tags
                    self._lang_hint,
                )
            except Exception as e:
                logger.error(f"Barge-in verification STT failed: {e}")
                self._barge_in_cooldown_until = time.monotonic() + (
                    VAD_BARGE_IN_COOLDOWN_MS / 1000.0
                )
                self._rearm_barge_in()
                return

            # Strip any stray brackets/parens defensively; keep only real words.
            lexical = re.sub(r"\[[^\]]*\]|\([^\)]*\)", "", text or "").strip()
            reject = None
            if lexical:
                if self._script_lang(lexical) is None:
                    reject = "not in an expected language"
                elif self._is_echo_of_ai(lexical):
                    reject = "echo of the AI's own voice"
            if lexical and not reject and self.ai_is_speaking:
                logger.info(f"Barge-in verified by STT: {lexical[:60]!r}")
                await self._handle_barge_in()
            else:
                if reject:
                    logger.info(f"Barge-in rejected ({reject}): {lexical[:60]!r}")
                else:
                    logger.debug(
                        "Barge-in candidate rejected (no real speech in snapshot)."
                    )
                self._barge_in_cooldown_until = time.monotonic() + (
                    VAD_BARGE_IN_COOLDOWN_MS / 1000.0
                )
                self._rearm_barge_in()
        finally:
            self._barge_in_checking = False
            # Consumed by _handle_barge_in / _finish_turn if it was speech;
            # otherwise it was noise (or the AI stopped) — drop it.
            self._barge_capture = None

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
                try:
                    await self._turn_watchdog()
                except Exception as e:
                    logger.error(f"Turn watchdog error: {e}", exc_info=True)
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
                            # Keep listening while this is transcribed and answered:
                            # the "end" may just be a pause mid-sentence.
                            self._begin_window()
                            self._continuation = True
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
                await self._release_held_audio()
                if not self._window_active:
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
                    language_code=self._lang_hint,
                    keyterms=self._stt_keyterms if STT_KEYTERMS_ENABLED else None,
                )
            except Exception as e:
                logger.error(f"ElevenLabs STT failed: {e}")
                text = ""

            text = (text or "").strip()
            if not text:
                logger.info("Empty transcript; reopening listening window.")
                await self._release_held_audio()
                if not self._window_active:
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
                await self._release_held_audio()
                if not self._window_active:
                    self._begin_window()
                return
            # Mostly in scripts the patient doesn't speak (e.g. '我就是', 'أقول'):
            # the patient said something STT could not recognise. Don't pass the
            # garbage on, but tell the model so it asks them to repeat instead of
            # staying silent. Not saved as a patient message.
            unclear = self._script_lang(lexical) is None
            if unclear and self._turn_open and self._turn_audio_started_at is None:
                # Unrecognisable sound after a pause, while a reply is pending:
                # treat it as noise rather than replacing the reply with a
                # "please repeat".
                logger.info(f"Unrecognisable speech after a pause ({text!r}); ignoring it.")
                await self._release_held_audio()
                if not self._window_active:
                    self._begin_window()
                return
            if unclear:
                logger.info(f"Transcript not in an expected language ({text!r}); telling the model the audio was unclear.")
                text = UNCLEAR_AUDIO_NOTICE
            else:
                logger.info(f"🗣️ Transcript injected: {text!r}")
                self._update_lang_hint(lexical)
            # The patient went on speaking after a pause, before any of the reply
            # was played: this is the rest of the same message. Send it as a
            # follow-up (the model drops its pending reply and answers both) and
            # keep both parts as one saved message.
            continuation = self._turn_open and self._turn_audio_started_at is None
            if continuation:
                logger.info("Patient continued after a pause; adding to the same turn.")
                self._discard_held_audio()
                self.current_ai_text = ""
                # A superseded reply that is still being generated would keep
                # streaming: drop it until Gemini confirms the interrupt. One that
                # already finished sends nothing more (and no interrupt), so
                # muting would only swallow the new reply.
                if self._turn_activity and not self._turn_gen_done:
                    self._suppress_ai_audio = True
                barge = self._suppress_ai_audio
                if not unclear:
                    self.current_user_text = f"{self.current_user_text} {text}".strip()
            else:
                await self._release_held_audio()
                # A barge-in left the interrupted turn open: persist what was said in
                # it before this new turn takes over.
                barge = self._suppress_ai_audio
                if barge and self._turn_open:
                    old_user = self.current_user_text.strip()
                    old_ai = self.current_ai_text.strip()
                    if old_user or old_ai:
                        asyncio.create_task(self.save_turn_messages(old_user, old_ai))
                    self.current_ai_text = ""
                self.current_user_text = "" if unclear else text
            # Track this as the prompt to re-send if the model returns an empty
            # turn, and reset the per-turn output/ retry guards for the new turn.
            self._last_injected_text = text
            self._empty_turn_retried = False
            self._turn_saw_output = False
            # Inject as a completed user turn. The window reopens when the turn
            # closes. Audio stays suppressed until the interrupted turn closes
            # (see _mark_turn_sent / _end_stale_close).
            await self.input_queue.put({"text": text, "barge": barge})
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

                    # While the AI is speaking, watch for a barge-in. The energy
                    # detector is only a cheap CANDIDATE trigger — servo/motor
                    # noise can trip it — so when it fires we snapshot ~1s of
                    # pre-roll and hand it to STT verification, which decides
                    # whether real speech is present before actually interrupting.
                    if self.ai_is_speaking:
                        if self._barge_capture is not None:
                            self._barge_capture.append(frame)
                        if (
                            self._barge_in is not None
                            and not self._barge_in_checking
                            and time.monotonic() >= self._barge_in_cooldown_until
                        ):
                            self._barge_in.push_audio(frame)
                            if self._barge_in.saw_speech:
                                self._barge_in_checking = True
                                self._barge_capture = list(self._preroll)
                                snapshot = (
                                    np.concatenate(self._barge_capture)
                                    if self._barge_capture
                                    else np.array([], dtype=np.int16)
                                )
                                # Disarm the energy detector while STT runs; it is
                                # re-armed (or the interrupt fires) in _verify.
                                self._barge_in = None
                                asyncio.create_task(
                                    self._verify_barge_in(snapshot)
                                )
                        return

                    # Normal listening: buffer the utterance and feed the energy
                    # VAD while a window is open (half-duplex).
                    if not self._window_active or self._eos is None:
                        return
                    self._mic_buf.append(frame)
                    self._eos.push_audio(frame)
                    return

                elif msg_type_byte == 0x01:
                    jpeg = bytes(payload_data)
                    # Latest frame, for the adjust_camera orchestrator.
                    self.latest_frame_b64 = base64.b64encode(jpeg).decode('utf-8')
                    self._latest_frame_at = time.monotonic()
                    # Fulfil pending snapshot requests (view_camera).
                    waiters, self._frame_waiters = self._frame_waiters, []
                    for fut in waiters:
                        if not fut.done():
                            fut.set_result(jpeg)
                    # Live feed: forward to Gemini only while the app's camera
                    # button is on.
                    if self._camera_feed_on:
                        await self.input_queue.put({"image": jpeg})
                
                elif msg_type_byte == 0x02:
                    data = json.loads(payload_data.decode('utf-8'))
                    if data.get("type") == "text":
                        await self.input_queue.put({"text": data.get("content") or data.get("data")})
                    elif data.get("type") == "track_offset":
                        await self._handle_track_offset(data)
                    elif data.get("type") == "camera_feed":
                        self._camera_feed_on = bool(data.get("enabled"))
                        logger.info(f"Camera feed to Gemini {'ON' if self._camera_feed_on else 'OFF'} (app camera button).")
                
                return

            if text_data:
                # Fallback for old text protocol.
                data = json.loads(text_data)
                msg_type = data.get("type")
                if msg_type == "audio":
                    # NEVER forward mic audio to Gemini. This model is driven only
                    # by injected TEXT (mic → energy VAD → ElevenLabs → text), and
                    # sending audio makes the Live API close the socket with
                    # 1007 "CONTENT_TYPE_AUDIO not supported for this model
                    # configuration". Audio must go through the 0x00 binary path.
                    logger.debug("Ignoring legacy JSON 'audio' frame (audio is never sent to Gemini).")
                elif msg_type == "image":
                    if self._camera_feed_on and data.get("data"):
                        await self.input_queue.put({"image": base64.b64decode(data["data"])})
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

        # 2. Build System Instruction (base). The "Recent conversation history"
        # section is appended fresh on every (re)connect below, because Gemini
        # Live keeps no server-side memory: after a mid-session disconnect the
        # new session must be re-seeded with the latest turns from the DB or the
        # conversation context is lost across the reconnect.
        system_instruction = f"""You are CarePAL, a compassionate AI healthcare assistant for home-bound patients.

MOST IMPORTANT STYLE RULE — applies to every reply, in every language:
Never add a medical disclaimer and never tell the patient to see, ask or consult a doctor or healthcare professional themselves. Checking with the doctor is YOUR job (with the 'contact_doctor' tool). Do not say things like:
  • "This is not medical advice or diagnosis" / "please consult a healthcare professional"
  • "ഇത് വൈദ്യോപദേശമോ രോഗനിർണ്ണയമോ അല്ല" / "ഒരു ഡോക്ടറെ സമീപിക്കുക" / "ഡോക്ടറോട് ചോദിക്കുക"
  • "यह चिकित्सा सलाह या निदान नहीं है" / "किसी स्वास्थ्य पेशेवर से परामर्श लें"
  • "இது மருத்துவ ஆலோசனை அல்ல" / "மருத்துவரை அணுகவும்"
Instead, give your helpful answer and, when the doctor's view would genuinely help, offer: "Shall I check with Dr. <doctor's name> about this?" (in the patient's language). Make this offer at most once or twice per topic in a conversation; if the patient declines or doesn't take it up, don't offer again for that topic. Don't open a conversation with such an offer. For emergencies only, tell them to call the doctor or 112 immediately.

Context:
- Patient Name: {context['name']}
- Age: {context['age']}
- Gender: {context['gender']}
- Current date and time (session start): {self._now_str()}
- Location: {context.get('location') or "Unknown (ask the patient which town they are in if you need it, e.g. for weather)"}
- Doctor: {context.get('doctor') or "Not recorded"}
- Preferred pharmacy: {context.get('pharmacy') or "Not recorded"}

Personal notes about the patient (kept from past conversations; use them naturally to make the conversation personal, never recite them or mention that you keep notes):
{context.get('personal_notes') or "None yet."}

Recent Vitals (Last 7 Days, plus the last known value of any vital not measured in that period):
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

4. Seeing: you only see the patient when they turn on the camera feed with the camera button in the app (you then receive about one camera image per second). Whenever you need to see something — a device reading, a medicine, a wound, whether the patient is okay — and you have no current image, call 'view_camera' to take a single snapshot; it works even when the feed is off. Tell the patient briefly that you are taking a look. Never describe or guess what you cannot currently see.

5. You can search the internet (Google Search) for current information: weather, news, sports scores, festival dates, opening hours, prices, or any general question. Search whenever the answer depends on today's information or on facts you are not sure of — never guess. For weather, use the patient's location; if it is unknown, ask which town they are in. Summarise results in one or two short sentences in the patient's language. Do not volunteer distressing news unless asked, and do not use search results to diagnose or change medical treatment.

6. Contacting the doctor: call 'contact_doctor' to send the patient's doctor a QUESTION (when the patient wants the doctor's opinion, or something needs a doctor's judgement: a new or worsening symptom, a possible medicine side effect, wanting to change or stop a medicine, readings that stay abnormal over several days) or a NOTIFICATION (an important event the doctor should know about, such as a fall or several days of missed doses). Do not send minor, routine details (a single slightly high reading, ordinary meals, mild everyday complaints) unless the patient specifically asks you to tell or ask the doctor. If you are the one suggesting it, first ask the patient briefly whether they would like you to ask the doctor; if the patient asks you to, just send it. Write the message clearly for a doctor (what happened, since when, relevant readings and medicines) and include the patient's own words. The doctor replies later through the app, not during this conversation: tell the patient so, and never present your own guess as the doctor's answer. Asking and confirming things with the doctor is YOUR job, not the patient's: never tell the patient to ask, check with, consult or confirm with their doctor (or "a healthcare professional") themselves. Whenever something needs the doctor's input, offer to ask the doctor for them and use 'contact_doctor'. Never add disclaimers such as "this is not medical advice or diagnosis" or "please consult a doctor / healthcare professional", in any language; the patient finds them repetitive. Give your helpful answer, and when a doctor's view would genuinely help, end with an offer instead, e.g. "Shall I check with Dr. <doctor's name> about this?" This is not for emergencies: for anything that sounds urgent (chest pain, trouble breathing, fainting, signs of stroke, severe bleeding) tell the patient to call the doctor's phone or emergency services (112) right away, and also send an URGENT notification.

7. The patient's preferred pharmacy details are in the context above: share them when the patient needs a refill or asks. You cannot place orders.

Rules:
- Speak clearly and warmly.
- The camera tracks the patient automatically. Only call 'adjust_camera' when the automated tracking is not keeping up, or when you specifically want to look somewhere.
- Do NOT call 'adjust_camera' repeatedly for small adjustments – trust the autonomous tracking.
- If you see a medical device, ask if you should record the reading.
- If the patient seems distressed, offer to call for help (simulated).
- Use the 'record_vital_reading' tool to save health data.
- Time: the patient is in India (IST). Every message you receive starts with a "[Time now: ...]" tag added by the system with the current IST time; always use the latest tag for anything time-related (greetings, "what time is it", medication timing). Never read the tag aloud or mention it.
- When you have a free moment in the conversation, check if there are any medications to be taken and whether the last dose was taken.
- The patient's words reach you through automatic speech recognition, which often mishears words, especially Malayalam mixed with English, so some messages will be partly garbled. Never reply only that you did not understand. Work out the most likely meaning from the words you can recognise and the conversation so far, and respond to that. If you are unsure, say what you think they meant and check (for example "Did you mean you just woke up?"). For anything important (medicines, symptoms, readings), always confirm what you understood. Text in Telugu or Kannada script is the patient's Malayalam transcribed in the wrong script: read it for its meaning.
- A message starting with [UNCLEAR_AUDIO] means the patient spoke but no words could be recognised at all; briefly and kindly ask them to repeat it.

Activity Logging (IMPORTANT):
- CRITICAL — DO NOT RE-LOG HISTORY: The "Recent conversation history" section below is
  PAST context that has ALREADY been logged. You must NEVER call 'log_patient_activity'
  for anything that appears in that history. At the start of a session do NOT emit any
  activity-log tool calls to "catch up" on the history — those events are already recorded.
  Only ever log NEW events that the patient states LIVE in the current, ongoing turn.
- You MUST silently call 'log_patient_activity' whenever you observe ANY of the following live during the current conversation turn — without prompting the patient and without mentioning that you are logging:
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
                    types.FunctionDeclaration(
                        name="contact_doctor",
                        description=(
                            "Send a question or a notification to the patient's doctor. Saved for the doctor, "
                            "who replies later through the app (not in this conversation). Use only for things "
                            "that need a doctor's opinion or that the doctor should know about, or when the "
                            "patient asks; not for minor routine details. Asking or confirming with the doctor is "
                            "CarePal's responsibility: never tell the patient to ask or consult the doctor "
                            "themselves; offer to ask on their behalf with this tool instead."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "kind": types.Schema(type="STRING", description="QUESTION (needs the doctor's answer) | NOTIFICATION (for the doctor's information)"),
                                "category": types.Schema(type="STRING", description="MEDICATION | SYMPTOM | VITALS | APPOINTMENT | OTHER"),
                                "urgency": types.Schema(type="STRING", description="ROUTINE | SOON (within a day) | URGENT"),
                                "subject": types.Schema(type="STRING", description="Short subject line, e.g. 'Dizziness after evening dose'."),
                                "message": types.Schema(type="STRING", description="The question or update written for the doctor: what happened, since when, relevant readings and medicines."),
                                "patient_words": types.Schema(type="STRING", description="What the patient said about it, in their own words."),
                            },
                            required=["kind", "subject", "message"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="view_camera",
                        description=(
                            "Take one fresh snapshot from the patient's camera so you can see something: "
                            "a device reading, a medicine strip or label, a wound or rash, the patient, the room. "
                            "Works even when the live camera feed is off. The image arrives in the next message — "
                            "do not describe or guess anything about it until you receive it."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "reason": types.Schema(
                                    type="STRING",
                                    description="What you want to look at, e.g. 'read the BP monitor'."
                                )
                            }
                        )
                    ),
                ]
            )
        ]
        # 3.x Live models run tools NON_BLOCKING by default (the model keeps going
        # without waiting); the handlers here assume it waits for each response.
        for tool in tools:
            for fd in tool.function_declarations:
                fd.behavior = types.Behavior.BLOCKING
        # Built-in Google Search grounding (weather, news, anything current). It
        # runs server-side: no tool_call reaches us, the model just speaks the
        # answer. Billed per search query (Gemini 3: 5,000/month free, then
        # $14 per 1,000).
        tools.append(types.Tool(google_search=types.GoogleSearch()))

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

        # Greet only once per connection lifetime (not on every silent reconnect).
        greeted = False
        # System instruction of the current Gemini session; reused verbatim when
        # resuming it (the server restores the conversation itself).
        session_instruction = None

        while not self.stop_event.is_set():
            resuming = self._resume_handle is not None
            got_message = False
            try:
                if not resuming or session_instruction is None:
                    # Fresh session: seed it with the latest conversation history
                    # from the DB so context carries across reconnects. (Also
                    # (re)binds self.db_session.) On the first connect this is the
                    # pre-session history; on a non-resumable reconnect it includes
                    # everything said this session.
                    recent_messages_str = await self.get_recent_messages_context()
                    session_instruction = (
                        system_instruction
                        + "\n\nRecent conversation history (READ-ONLY context, already "
                        + "logged — do NOT call log_patient_activity for anything here):\n"
                        + recent_messages_str
                    )
                config = types.LiveConnectConfig(
                    response_modalities=["AUDIO"],
                    media_resolution="MEDIA_RESOLUTION_MEDIUM",
                    system_instruction=types.Content(
                        parts=[types.Part(text=session_instruction)]
                    ),
                    tools=tools,  # Pass tool definitions
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sulafat")
                        )
                    ),
                    realtime_input_config=realtime_input_config,
                    # Text of what the AI says: saved as the AGENT message, used for
                    # the STT language hint and the barge-in echo filter.
                    output_audio_transcription=types.AudioTranscriptionConfig(),
                    # Resumable sessions survive connection resets (Gemini closes
                    # every connection after ~10 min, announced by go_away).
                    session_resumption=types.SessionResumptionConfig(
                        handle=self._resume_handle
                    ),
                    # Without compression, audio sessions end after ~15 minutes.
                    context_window_compression=types.ContextWindowCompressionConfig(
                        sliding_window=types.SlidingWindow()
                    ),
                )
                async with client.aio.live.connect(model=MODEL, config=config) as session:
                    self.session = session
                    self._planned_reconnect = False
                    self.current_user_text = ""
                    self.current_ai_text = ""
                    # New connection: any turn in flight on the old one is gone.
                    # Open a listening window so the user can speak (no audio is
                    # ever sent to the model, so it will not speak unprompted) —
                    # unless one is already open and may be capturing speech.
                    self.ai_is_speaking = False
                    self._barge_in = None
                    self._barge_in_checking = False
                    self._barge_in_cooldown_until = 0.0
                    self._suppress_ai_audio = False
                    self._expect_stale_close = False
                    self._turn_open = False
                    self._tools_outstanding = 0
                    self._continuation = False
                    self._discard_held_audio()
                    self._turn_saw_output = False
                    self._last_injected_text = ""
                    self._empty_turn_retried = False
                    if not self._window_active:
                        self._begin_window()
                    logger.info(
                        "Connected to Gemini Live"
                        + (" (resuming previous session)" if resuming else "")
                    )

                    # Start the sender loop
                    sender_task = asyncio.create_task(self.sender_loop())

                    # On the very first connect, prompt the AI to speak first so
                    # the patient is greeted instead of facing silence. This is a
                    # system trigger (not the patient's speech), so it is not
                    # stored as a user message. Skipped on reconnects to avoid a
                    # jarring re-greeting mid-conversation.
                    if not greeted:
                        greeted = True
                        await self.input_queue.put({
                            "text": (
                                "[SESSION_START] The session just began. Greet the "
                                "patient warmly and briefly by name, weaving in any "
                                "relevant context (e.g. a pending medication or a "
                                "follow-up from recent history) only if natural. "
                                "Keep it to one or two short sentences. Do NOT log "
                                "any activity for this greeting."
                            )
                        })

                    # Receiver loop
                    logger.info("Starting receiver loop")
                    try:
                        while not self.stop_event.is_set() and not self._planned_reconnect:
                            async for response in session.receive():
                                if self.stop_event.is_set():
                                    break
                                got_message = True
                                self._last_server_msg_at = time.monotonic()
                                await self._handle_server_message(response, session)

                            logger.debug("Receiver loop finished (turn complete). Re-entering...")
                            if self.stop_event.is_set():
                                break

                            # Small delay to prevent busy looping if connection is dead but not raising error
                            await asyncio.sleep(0.05)

                    except Exception as inner_e:
                        if self._planned_reconnect:
                            pass
                        elif self._is_transient_disconnect(inner_e):
                            logger.warning(
                                f"Gemini Live connection dropped ({inner_e}); "
                                "reconnecting."
                            )
                        else:
                            logger.error(
                                f"Error inside receiver loop: {inner_e}",
                                exc_info=True,
                            )

                    sender_task.cancel()
                    try:
                        await sender_task
                    except asyncio.CancelledError:
                        pass
                    if self._go_away_task and not self._go_away_task.done():
                        self._go_away_task.cancel()
                    self._go_away_task = None

                if self.stop_event.is_set():
                    break
                if resuming and not got_message:
                    logger.warning("Session resumption failed; starting a fresh session.")
                    self._resume_handle = None
                if self._planned_reconnect:
                    logger.info("Reconnecting to Gemini Live (planned, after go_away).")
                    continue

                logger.warning("Gemini session disconnected silently, reconnecting in 1s...")
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("Gemini session cancelled")
                break
            except Exception as e:
                if self.stop_event.is_set():
                    break
                if resuming and not got_message:
                    logger.warning(f"Session resumption failed ({e}); starting a fresh session.")
                    self._resume_handle = None
                elif self._is_transient_disconnect(e):
                    logger.warning(
                        f"Gemini Live connection dropped ({e}); reconnecting in 2s..."
                    )
                else:
                    logger.error(f"Gemini session error: {e}", exc_info=True)
                    logger.warning("Gemini session crashed, reconnecting in 2s...")
                await asyncio.sleep(2)

        logger.info("Exiting run_gemini_session")

    async def _handle_server_message(self, response, session):
        """Handle one message from Gemini Live (see the turn-tracking notes at the top)."""
        server_content = getattr(response, "server_content", None)
        # Audio sent while waiting for the interrupted turn to close belongs to
        # that turn: it is dropped and says nothing about the new turn.
        stale = self._expect_stale_close

        # 1. Model output parts. Read parts directly (rather than response.data /
        # response.text) so thought parts are recognized and the SDK does not warn
        # about mixed part types.
        function_calls = []
        model_turn = server_content.model_turn if server_content else None
        for part in (model_turn.parts or []) if model_turn else []:
            if part.function_call:
                function_calls.append(part.function_call)
            elif part.inline_data and part.inline_data.data:
                if self._suppress_ai_audio:
                    # Interrupted turn's trailing audio: discard, don't replay it.
                    # Before the user's new message is sent this still counts as
                    # output of the interrupted turn (so it is never re-prompted).
                    if not stale:
                        self._turn_activity = True
                        self._turn_saw_output = True
                    continue
                if not self._turn_open:
                    self._open_implicit_turn()
                self._turn_activity = True
                self._turn_saw_output = True
                self._turn_gen_done = False
                if self._holding_for_continuation or self._patient_continuing():
                    # The patient is speaking again after a pause: hold the reply
                    # until we know whether they were adding to their message.
                    if not self._holding_for_continuation:
                        logger.info("Holding AI reply: the patient is still speaking.")
                        self._holding_for_continuation = True
                        self._hold_started_at = time.monotonic()
                    self._held_audio.append(part.inline_data.data)
                    continue
                await self._start_ai_audio()
                self._turn_audio_bytes += len(part.inline_data.data)
                await self.send(bytes_data=bytes([0x00]) + part.inline_data.data)
            elif part.thought:
                if not stale:
                    self._turn_activity = True
                    self._turn_gen_done = False
            elif part.text:
                logger.debug(f"[AI_SPEAKING={self.ai_is_speaking}] Received text: {part.text[:50]}...")
                if not stale:
                    self._turn_activity = True
                    self._turn_saw_output = True
                await self.send(bytes_data=bytes([0x02]) + json.dumps({
                    "type": "text",
                    "content": part.text
                }).encode('utf-8'))

        # Tool calls, delivered on response.tool_call or inside model_turn. Counted
        # before the turn signals below, which may arrive in the same message.
        tool_call = getattr(response, "tool_call", None)
        if tool_call and tool_call.function_calls:
            function_calls.extend(tool_call.function_calls)
        if function_calls:
            if not self._turn_open:
                self._open_implicit_turn()
            # A tool call counts as real model output for empty-turn detection.
            self._turn_activity = True
            self._turn_saw_output = True
            self._tools_outstanding += len(function_calls)

        # Google Search runs server-side; log its queries (each one is billed).
        grounding = server_content.grounding_metadata if server_content else None
        if grounding and grounding.web_search_queries:
            logger.info(f"Web search: {grounding.web_search_queries}")

        # What the AI actually said (skipping the part the user cut off).
        if server_content and server_content.output_transcription:
            spoken = server_content.output_transcription.text
            if spoken and self._turn_open and not self._suppress_ai_audio:
                self.current_ai_text += spoken

        # 2. Server signals
        if server_content:
            if server_content.interrupted:
                logger.info(f"[AI_SPEAKING={self.ai_is_speaking}] Gemini signaled interrupt. Sending 0x03 to frontend.")
                await self.send(bytes_data=bytes([0x03]))
                self.ai_is_speaking = False
                self._barge_in = None
                if self._expect_stale_close:
                    self._end_stale_close()

            if server_content.generation_complete and not stale:
                self._turn_activity = True
                self._turn_gen_done = True

            if server_content.turn_complete:
                if self._expect_stale_close:
                    # Closes the interrupted turn, not the one just sent.
                    self._end_stale_close()
                elif not self._turn_open or not self._turn_activity:
                    # Gemini withholds turn_complete after tool calls until the
                    # next message; arriving before any new output, it belongs to
                    # an earlier turn and must not end (or "empty") this one.
                    logger.info("Ignoring stale turn_complete from an earlier turn.")
                elif self._holding_for_continuation:
                    # Reply held while the patient adds to their message; the
                    # continuation decides what happens to this turn.
                    logger.debug("turn_complete while a reply is held; waiting for the continuation.")
                elif self._tools_outstanding > 0:
                    # 3.x closes the turn as soon as it calls a tool, then speaks
                    # its follow-up once answered; the watchdog closes the turn
                    # after that follow-up (or after TURN_TOOL_FOLLOWUP_MS).
                    logger.debug("turn_complete while a tool call is unanswered; waiting for the follow-up.")
                else:
                    await self._finish_turn("turn_complete")

        # 3. Dispatch tool calls.
        for fc in function_calls:
            logger.info(f"Function call requested: {fc.name}")
            fc_args = dict(fc.args) if hasattr(fc, "args") and fc.args else {}
            fc_id = getattr(fc, 'id', None)
            if fc.name == "adjust_camera":
                command = fc_args.get("command", "")
                asyncio.create_task(self._run_tool(self.handle_adjust_camera(command, fc_id)))
            elif fc.name == "record_vital_reading":
                asyncio.create_task(self._run_tool(self.handle_record_vital(fc_args, fc_id)))
            elif fc.name == "log_patient_activity":
                asyncio.create_task(self._run_tool(self.handle_log_activity(fc_args, fc_id)))
            elif fc.name == "contact_doctor":
                asyncio.create_task(self._run_tool(self.handle_contact_doctor(fc_args, fc_id)))
            elif fc.name == "view_camera":
                asyncio.create_task(self._run_tool(self.handle_view_camera(fc_args, fc_id)))
            else:
                logger.warning(f"Unknown function call: {fc.name}")
                self._tools_outstanding = max(0, self._tools_outstanding - 1)

        # 4. Session lifecycle
        update = getattr(response, "session_resumption_update", None)
        if update and update.resumable and update.new_handle:
            self._resume_handle = update.new_handle

        go_away = getattr(response, "go_away", None)
        if go_away:
            logger.info(
                f"Gemini go_away: connection closes in {go_away.time_left}; "
                "reconnecting at the next pause."
            )
            if self._go_away_task is None or self._go_away_task.done():
                self._go_away_task = asyncio.create_task(self._reconnect_when_idle(session))

    async def _run_tool(self, handler):
        """Run a tool handler (which sends the tool response) and track it for
        turn closing (see TURN_TOOL_FOLLOWUP_MS)."""
        try:
            await handler
        finally:
            self._tools_outstanding = max(0, self._tools_outstanding - 1)
            self._last_tool_response_at = time.monotonic()

    async def _reconnect_when_idle(self, session):
        """
        After go_away, wait until nothing is in flight (no open turn, AI silent,
        no transcription running), then close the connection; the session loop
        reconnects at once with the resumption handle. If Gemini closes first,
        the normal reconnect path resumes the session the same way.
        """
        try:
            while not self.stop_event.is_set():
                if not (self._turn_open or self.ai_is_speaking or self._transcribing):
                    break
                await asyncio.sleep(0.1)
            if self.stop_event.is_set() or self._resume_handle is None:
                return
            self._planned_reconnect = True
            await session.close()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Planned reconnect: closing the old connection failed: {e}")

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
                    interrupting = self._suppress_ai_audio
                    self._mark_turn_sent()
                    if (
                        item.get("barge")
                        and interrupting
                        and INTERRUPT_WITH_ACTIVITY_SIGNALS
                    ):
                        # Stop the interrupted generation server-side; must be
                        # immediately followed by the new text (see constant).
                        await self.session.send_realtime_input(activity_start=types.ActivityStart())
                        await self.session.send_realtime_input(activity_end=types.ActivityEnd())
                    # The session (and its system prompt) can last hours across
                    # resumptions, so every message carries the current IST time.
                    text = f"[Time now: {self._now_str()}] {item['text']}"
                    parts = [types.Part(text=text)]
                    if item.get("image"):
                        # Snapshot for view_camera: an image inside a client turn
                        # is reliably seen (one sent with a tool response is not).
                        parts.append(types.Part.from_bytes(data=item["image"], mime_type="image/jpeg"))
                    logger.info(f"Sending text to Gemini: {text}" + (" [+ image]" if item.get("image") else ""))
                    await self.session.send_client_content(
                        turns=types.Content(role="user", parts=parts),
                        turn_complete=True,
                    )
                elif "image" in item:
                    # Live camera feed frame (camera button on).
                    await self.session.send_realtime_input(
                        video=types.Blob(data=item["image"], mime_type="image/jpeg")
                    )

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

        When the subject is lost (found=false), hand off to _handle_track_lost,
        which extrapolates the last motion direction and pans to search for it.
        """
        if not ENABLE_EDGE_TRACKING:
            return
        cfg = self._track_cfg
        now_ms = time.monotonic() * 1000.0

        found = bool(data.get("found", True))
        try:
            conf = float(data.get("conf", 1.0))
            dx = float(data.get("dx", 0.0))
        except (TypeError, ValueError):
            return

        # ── Subject lost → coast/search in the extrapolated direction ────────
        if not found or conf < cfg["min_conf"]:
            await self._handle_track_lost(now_ms)
            return

        # ── Subject visible → normal proportional tracking ───────────────────
        dx = max(-1.0, min(1.0, dx))
        # Buffer position for velocity extrapolation; drop samples out of window.
        self._track_hist.append((now_ms, dx))
        self._prune_track_hist(now_ms)
        # Re-acquired → cancel any in-progress search.
        if self._coasting:
            logger.info("[coast] subject re-acquired; ending search")
            self._coasting = False
            self._search_travel = 0.0

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

    def _prune_track_hist(self, now_ms: float):
        """Drop buffered position samples older than the history window."""
        window = self._track_cfg["history_ms"]
        hist = self._track_hist
        while hist and now_ms - hist[0][0] > window:
            hist.popleft()

    def _estimate_track_velocity(self, now_ms: float):
        """Horizontal offset velocity (dx units/sec) over the recent history
        window, or None if there isn't enough data to estimate it."""
        self._prune_track_hist(now_ms)
        hist = self._track_hist
        if len(hist) < 2:
            return None
        t0, x0 = hist[0]
        t1, x1 = hist[-1]
        dt = (t1 - t0) / 1000.0
        if dt <= 0.0:
            return None
        return (x1 - x0) / dt

    async def _handle_track_lost(self, now_ms: float):
        """Dead-reckoning search when the subject disappears.

        Starts a search only if the subject was genuinely moving when it vanished
        (a low-velocity disappearance is almost certainly a one-frame detection
        blip, so we hold). While searching, pan in the extrapolated direction each
        lost frame until either the cumulative travel cap or the timeout is hit,
        then give up and hold until the subject is re-acquired.
        """
        cfg = self._track_cfg
        if not cfg["coast_enable"]:
            return

        if not self._coasting:
            vel = self._estimate_track_velocity(now_ms)
            if vel is None or abs(vel) < cfg["coast_min_vel"]:
                return   # not moving (or no data) → treat as a blip, hold
            self._coasting = True
            self._coast_dir = 1 if vel > 0 else -1
            self._coast_start_ms = now_ms
            self._search_travel = 0.0
            logger.info(
                f"[coast] subject lost while moving (v={vel:.2f}/s); searching "
                f"{'right' if self._coast_dir > 0 else 'left'}"
            )

        # Stop conditions: searched the full arc, or lost for too long.
        if (self._search_travel >= cfg["search_max_deg"]
                or now_ms - self._coast_start_ms > cfg["coast_timeout_ms"]):
            return
        if now_ms - self._last_edge_pan_ms < cfg["cooldown_ms"]:
            return

        step = min(cfg["coast_step"], cfg["search_max_deg"] - self._search_travel)
        if step < 1.0:
            return
        delta = int(round(step)) * self._coast_dir
        if delta == 0:
            return
        self._search_travel += abs(delta)
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
        logger.debug(f"[pan] Sent delta={delta} to {group_name}")

    @database_sync_to_async
    def _save_doctor_query(self, params: dict) -> dict:
        """Persist a DoctorQuery (see agent.models) for the patient's doctor."""
        from .models import DoctorQuery
        from users.models import ClinicalRelationship

        try:
            patient = PatientProfile.objects.filter(user=self.user).first()
            if not patient:
                return {"success": False, "error": "No patient profile found"}

            def choice(value, field, default):
                value = str(value or "").strip().upper()
                valid = {c for c, _ in DoctorQuery._meta.get_field(field).choices}
                return value if value in valid else default

            # The patient's linked doctor account, primary physician first.
            links = list(
                ClinicalRelationship.objects.filter(patient=patient, is_active=True)
                .select_related('doctor')
            )
            link = next((r for r in links if r.role == 'PRIMARY'), links[0] if links else None)
            doctor_name = patient.doctor_name or (link.doctor.get_full_name() if link else "")

            # Supporting context: latest reading per vital, active medicines.
            vitals = {}
            for r in (VitalReading.objects.filter(patient=patient, is_deleted=False)
                      .select_related('vital_type').order_by('-measured_at')[:50]):
                if r.vital_type.code not in vitals:
                    vitals[r.vital_type.code] = {
                        'display': r.get_display_value(),
                        'measured_at': timezone.localtime(r.measured_at).isoformat(),
                    }
            medications = [
                f"{m.medication_name} {m.dosage} ({m.frequency})"
                for m in Medication.objects.filter(patient=patient, status='ACTIVE')
            ]

            query = DoctorQuery.objects.create(
                patient=patient,
                session=getattr(self, 'db_session', None),
                doctor=link.doctor if link else None,
                doctor_name=doctor_name,
                kind=choice(params.get('kind'), 'kind', 'QUESTION'),
                category=choice(params.get('category'), 'category', 'OTHER'),
                urgency=choice(params.get('urgency'), 'urgency', 'ROUTINE'),
                subject=str(params.get('subject') or '')[:200],
                message=str(params.get('message') or ''),
                patient_words=str(params.get('patient_words') or ''),
                context={'vitals': vitals, 'medications': medications},
            )
            logger.info(f"DoctorQuery created: id={query.id} {query.kind}/{query.urgency} '{query.subject}'")
            return {
                "success": True,
                "query_id": query.id,
                "doctor": doctor_name or "the patient's doctor",
                "note": "Saved for the doctor. The doctor replies later through the app, not in this conversation.",
            }
        except Exception as e:
            logger.error(f"Error saving doctor query: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def handle_contact_doctor(self, args: dict, fc_id):
        """'contact_doctor' tool: store the question/notification for the doctor."""
        result = await self._save_doctor_query(args or {})
        if fc_id and self.session:
            try:
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(id=fc_id, name="contact_doctor", response=result)]
                )
            except Exception as exc:
                logger.error(f"[contact_doctor] Failed to send tool response: {exc}")

    async def _request_camera_frame(self, timeout: float = CAMERA_SNAPSHOT_TIMEOUT_S):
        """Ask the app for one fresh camera frame; returns JPEG bytes or None."""
        fut = asyncio.get_running_loop().create_future()
        self._frame_waiters.append(fut)
        try:
            await self.send(bytes_data=b"\x02" + json.dumps({"type": "capture_frame"}).encode("utf-8"))
            return await asyncio.wait_for(fut, timeout)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"[camera] snapshot request failed: {e or 'timed out'}")
            return None
        finally:
            if fut in self._frame_waiters:
                self._frame_waiters.remove(fut)

    async def handle_view_camera(self, args: dict, fc_id):
        """
        'view_camera' tool: grab a snapshot from the app (even with the feed off)
        and show it to the model. Measured on 3.8 Live: an image sent alongside a
        tool response is ignored (the model guesses), but one sent as the next
        client turn is read correctly. So: answer the call first, then send the
        image as its own turn.
        """
        reason = (args or {}).get("reason", "")
        logger.info(f"[view_camera] requested ({reason!r})")
        jpeg = await self._request_camera_frame()
        if jpeg is None:
            result = {"success": False, "error": "The camera did not return an image (camera off or not ready). Ask the patient to check the camera."}
        else:
            result = {"success": True, "status": "Snapshot taken; the image follows in the next message."}
        if fc_id and self.session:
            try:
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(id=fc_id, name="view_camera", response=result)]
                )
            except Exception as exc:
                logger.error(f"[view_camera] Failed to send tool response: {exc}")
                return
        if jpeg is not None:
            await self.input_queue.put({
                "text": "[Camera snapshot from view_camera]",
                "image": jpeg,
            })
            logger.info(f"[view_camera] snapshot sent ({len(jpeg) // 1024} KB)")

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

            # The orchestrator needs to see the scene: with the live feed off there
            # is no recent frame, so take a snapshot first.
            if time.monotonic() - self._latest_frame_at > CAMERA_FRAME_FRESH_S:
                await self._request_camera_frame(timeout=3.0)

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
                logger.debug(f"[adjust_camera] Panned delta={delta}")

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


