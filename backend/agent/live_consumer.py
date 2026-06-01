
import os
import json
import logging
import asyncio
import base64
import numpy as np
import torch
from silero_vad import load_silero_vad
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
from medications.models import Medication, MedicationSchedule, MedicationAdherence
from users.models import User
from agent.models import AgentSession, AgentMessage
from agent.camera_pan_controller import CameraPanController

logger = logging.getLogger(__name__)

# Configure the model
# Configure the model
MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

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

        try:
            self.vad_model = load_silero_vad()
            self.ai_is_speaking = False
            self.silence_hangover_chunks = 0
            logger.info("Silero VAD model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            self.vad_model = None

        # Initialise the camera pan controller
        self.pan_controller = CameraPanController(
            user_id=getattr(self.user, 'id', None),
            channel_layer=self.channel_layer,
        )
        self.pan_controller.start()

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

            # 2. Active Medications
            active_meds = Medication.objects.filter(
                patient=patient,
                status='ACTIVE'
            )
            
            meds_summary = []
            for m in active_meds:
                schedule = m.schedules.first() # specific time
                time_str = f" at {schedule.time_of_day.strftime('%H:%M')}" if schedule else f" ({m.frequency})"
                meds_summary.append(f"- {m.medication_name} {m.dosage}{time_str}")
            
            meds_str = "\n".join(meds_summary) if meds_summary else "No active medications"

            return {
                "name": patient.user.get_full_name(),
                "age": str(patient.age) if hasattr(patient, 'age') else "Unknown", # Assuming age property
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
        if hasattr(self, 'pan_controller'):
            self.pan_controller.stop()
        if hasattr(self, 'task'):
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Gemini Live WebSocket disconnected")

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
                    # VAD Check before sending to Gemini
                    if self.vad_model is not None and len(payload_data) >= 1024: # 1024 bytes = 512 int16 samples
                        audio_int16 = np.frombuffer(payload_data, dtype=np.int16)
                        audio_float32 = audio_int16.astype(np.float32) / 32768.0
                        tensor = torch.from_numpy(audio_float32)
                        
                        try:
                            is_speech = False
                            is_confident_speech = False
                            max_amp = torch.max(torch.abs(tensor)).item()
                            for i in range(0, len(tensor), 512):
                                chunk = tensor[i:i+512]
                                if len(chunk) < 512:
                                    continue # Skip trailing short chunks
                                speech_prob = self.vad_model(chunk, 16000).item()
                                if speech_prob > 0.5:
                                    is_speech = True
                                if speech_prob > 0.75:
                                    is_confident_speech = True
                                    break
                            
                            prev_vad = getattr(self, 'last_vad_state', False)
                            
                            if is_speech:
                                self.silence_hangover_chunks = 15
                            
                            if is_speech and not prev_vad:
                                print(f"🗣️ VAD Triggered: Speech START (Max Amp: {max_amp:.4f})", flush=True)
                            elif not is_speech and prev_vad:
                                print(f"🔇 VAD Triggered: Speech END (Max Amp: {max_amp:.4f})", flush=True)
                                
                            self.last_vad_state = is_speech

                            if not is_speech:
                                if getattr(self, 'silence_hangover_chunks', 0) > 0:
                                    self.silence_hangover_chunks -= 1
                                    # DO NOT drop! Let Gemini hear the end-of-speech silence naturally.
                                else:
                                    print(f"Dropped silent audio. Max Amp: {max_amp:.4f}", flush=True)
                                    return # Drop silence packet
                                
                            # Fast interrupt: only trigger if we have HIGH CONFIDENCE speech
                            # (prob > 0.75). The lower 0.5 threshold above is only for
                            # silence detection. This prevents echo at partial amplitude
                            # from firing a false interrupt when the AI is speaking.
                            if getattr(self, 'ai_is_speaking', False) and is_confident_speech:
                                print("VAD detected confident speech while AI speaking. Triggering FAST INTERRUPT!", flush=True)
                                await self.send(bytes_data=bytes([0x03]))
                                self.ai_is_speaking = False
                        except Exception as ve:
                            print(f"VAD error: {ve}", flush=True)

                    # Gemini v1beta multimodal currently expects base64 or raw via specific fields 
                    # We wrap in base64 here to keep Gemini SDK happy for now.
                    b64_audio = base64.b64encode(payload_data).decode('utf-8')
                    await self.input_queue.put({
                        "mime_type": "audio/pcm;rate=16000",
                        "data": b64_audio
                    })

                elif msg_type_byte == 0x01:
                    b64_image = base64.b64encode(payload_data).decode('utf-8')
                    # Store latest frame for manual-override inference
                    self.latest_frame_b64 = b64_image
                    # Feed raw bytes to the autonomous pan controller
                    has_ctrl = hasattr(self, 'pan_controller')
                    print(f"[FRAME] 0x01 received | payload={len(payload_data)}B | has_controller={has_ctrl}", flush=True)
                    if has_ctrl:
                        self.pan_controller.process_frame(payload_data)
                        print(f"[FRAME] process_frame called, _latest_frame is now set={self.pan_controller._latest_frame is not None}", flush=True)
                    await self.input_queue.put({
                        "mime_type": "image/jpeg",
                        "data": b64_image
                    })
                
                elif msg_type_byte == 0x02:
                    data = json.loads(payload_data.decode('utf-8'))
                    if data.get("type") == "text":
                        await self.input_queue.put({"text": data.get("content") or data.get("data")})
                
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
            if not self.user:
                return {"success": False, "error": "No user context"}

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
  • Patient mentions eating a meal or snack (activity_type: MEAL)
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

Recent conversation history:
{recent_messages_str}
"""

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
                                    description="Structured extras. MEAL→{meal_items,appetite}. SYMPTOM→{symptom_name,severity,duration,body_part}. EXERCISE→{activity_name,duration_minutes,intensity}. SLEEP→{hours_slept,quality}. MOOD→{mood_description,energy_level}."
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
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )

        while not self.stop_event.is_set():
            try:
                async with client.aio.live.connect(model=MODEL, config=config) as session:
                    self.session = session
                    self.current_user_text = ""
                    self.current_ai_text = ""
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
                                    self.ai_is_speaking = True
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
                                    if getattr(server_content, 'input_transcription', None):
                                        t = server_content.input_transcription
                                        if hasattr(t, 'text') and t.text:
                                            self.current_user_text += t.text
                                        elif hasattr(t, 'parts'):
                                            for p in t.parts:
                                                if hasattr(p, 'text') and p.text:
                                                    self.current_user_text += p.text

                                    if getattr(server_content, 'interrupted', False):
                                        logger.info(f"[AI_SPEAKING={self.ai_is_speaking}] Gemini signaled interrupt. Sending 0x03 to frontend.")
                                        await self.send(bytes_data=bytes([0x03]))
                                        self.ai_is_speaking = False

                                    if getattr(server_content, 'turn_complete', False):
                                        logger.info(f"[AI_SPEAKING={self.ai_is_speaking}] Server content: turn_complete=True. Resetting flag.")
                                        self.ai_is_speaking = False
                                        
                                        user_t = self.current_user_text.strip()
                                        ai_t = self.current_ai_text.strip()
                                        if user_t or ai_t:
                                            asyncio.create_task(self.save_turn_messages(user_t, ai_t))
                                            
                                        self.current_user_text = ""
                                        self.current_ai_text = ""
                                        
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
                    # It's a text message
                    logger.info(f"Sending text to Gemini: {item['text']}")
                    await self.session.send(input=item["text"], end_of_turn=True)
                else:
                    # It's media (audio/image) dict {"mime_type":..., "data":...}
                    # Send dict with Base64 exactly as the SDK expects for LiveConnect!
                    await self.session.send(input=item)
                    
        except asyncio.CancelledError:
            logger.info("Sender loop cancelled")
            pass
        except Exception as e:
            logger.error(f"Error in sender loop: {e}", exc_info=True)

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
        Manual-override entry point called when the Live AI invokes 'adjust_camera'.

        Passes the command + current frame to an orchestrator model which decides:
          • switch_mode  – change the pan controller to tracking or look_around
          • pan          – send an immediate delta pan and enter manual_override for 30s

        After 30 seconds the pan controller automatically reverts to tracking.
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
The camera system has three modes:
  - "tracking"        : computer-vision face/body tracking (default)
  - "look_around"     : slow left/right sweep searching for a person
  - "manual_override" : a one-off pan command; tracking resumes after 30 s

Given the command (and the current camera frame when available), choose the
best action and return ONLY a JSON object – no markdown, no extra text.

Possible response shapes:

  Switch mode:
    {"action": "switch_mode", "mode": "tracking"}
    {"action": "switch_mode", "mode": "look_around"}

  Immediate pan (also activates manual_override for 30 s):
    {"action": "pan", "delta": <INT>}
    Positive delta = pan right. Negative delta = pan left. Range ±10 … ±60.

Decision guide:
  "look around / find patient / patient not visible"        → switch_mode look_around
  "switch to face tracking / start tracking"               → switch_mode tracking
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

            controller = getattr(self, 'pan_controller', None)
            act = action.get('action')

            if act == 'switch_mode':
                mode = action.get('mode', 'tracking')
                if controller:
                    controller.set_mode(mode)
                result_msg = f"Switched camera to '{mode}' mode."
                logger.info(f"[adjust_camera] Mode switched to '{mode}'")

            elif act == 'pan':
                delta = int(action.get('delta', 0))
                if delta != 0:
                    if controller:
                        controller.enter_manual_override()
                    await self._send_hardware_pan(delta)
                    result_msg = f"Panned camera by {delta}° (manual override active for 30 s)."
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


