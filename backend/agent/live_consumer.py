
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
            # For testing/dev, maybe default to first patient or handle error
            # For now, we'll try to find a patient profile if user is valid
            pass

        try:
            self.vad_model = load_silero_vad()
            self.ai_is_speaking = False
            self.silence_hangover_chunks = 0
            logger.info("Silero VAD model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            self.vad_model = None
            
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
                    # Store latest frame for panning inference
                    self.latest_frame_b64 = b64_image
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
1. You have access to a camera. You can move it left or right to see the patient better. Do not ask confirmation from the user to control the panning, do it as you need to see better or look around.
2. You can record vital signs if the patient shows you a device or tells you the reading. pan to see a better view of the device if needed.

Rules:
- Speak clearly and warmly.
- If you see a medical device, ask if you should record the reading.
- If the patient seems distressed, offer to call for help (simulated).
- Proactively pan the camera to keep the user in center of the view.
- Use the 'adjust_camera' tool to adjust your view if needed by providing a descriptive textual command (e.g., 'Pan left', 'User not centered', 'look around for the patient').
- Use the 'record_vital_reading' tool to save health data.
- Considering that the user is in GMT +5:30, see if there are any medcations to be taked, and check if the user has taken the last medication when you get free time in the conversation..

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
                    )
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
                                    if fc.name == "adjust_camera":
                                        command = fc.args.get("command", "") if hasattr(fc, "args") else ""
                                        fc_id = getattr(fc, 'id', None)
                                        asyncio.create_task(self.handle_adjust_camera(command, fc_id))
                                            
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

    async def handle_adjust_camera(self, command, fc_id):
        """
        Takes a textual command from Gemini Voice AI, analyzes the latest
        camera frame using Gemini 3 Flash Preview, and sends a command to the hardware WebSocket.
        """
        logger.info(f"[TOOL EXECUTION START] adjust_camera invoked | Command: '{command}' | Function Call ID: {fc_id}")
        result_msg = "Command executed successfully and sent to hardware."
        
        try:
            if not getattr(self, 'latest_frame_b64', None):
                logger.warning("[adjust_camera] No camera frame available in self.latest_frame_b64 to process the command.")
                result_msg = "No camera frame available to execute the command."
            else:
                logger.info("[adjust_camera] Found latest camera frame. Preparing to call Gemini 3 Flash Preview.")
                
                # Initialize Gemini API client
                api_key = os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None)
                client = genai.Client(api_key=api_key)
                
                system_instruction = '''You are a CarePal hardware controller. 
You are given the latest camera frame and a textual command from a voice assistant (e.g., 'Pan left', 'Patient not visible', 'User not centered').
Determine the optimal pan movement for the camera motor to fulfill the command and keep the patient in view.
Return ONLY a JSON object exactly like this:
{
    "type": "set_pan_position",
    "mode": "delta",
    "value": <INT>
}
Use "mode": "delta", with "value" in degrees. Negative means move right, positive means move left.
Typical magnitudes are 10 to 30 degrees. Do not include markdown formatting.'''
                
                image_bytes = base64.b64decode(self.latest_frame_b64)
                
                logger.info(f"[adjust_camera] Calling Gemini with prompt: 'Command: {command}'...")
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model='gemini-3-flash-preview',
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                        f"Command: {command}"
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1
                    )
                )
                
                logger.info(f"[adjust_camera] Received response from Gemini 3 Flash: {repr(response.text)}")
                
                # Parse JSON response
                response_text = response.text.strip()
                if response_text.startswith('```json'):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith('```'):
                    response_text = response_text[3:-3].strip()
                    
                import json
                hardware_command = json.loads(response_text)
                logger.info(f"[adjust_camera] Parsed hardware command successfully: {hardware_command}")
                
                # Send to hardware via Django Channels
                if hasattr(self, 'channel_layer') and self.channel_layer and self.user and self.user.id:
                    group_name = f"hardware_user_{self.user.id}"
                    logger.info(f"[adjust_camera] Dispatching payload {hardware_command} to channel group: {group_name}")
                    await self.channel_layer.group_send(
                        group_name,
                        {
                            "type": "device.command",
                            "payload": hardware_command
                        }
                    )
                    logger.info(f"[adjust_camera] Payload dispatched successfully to {group_name}.")
                else:
                    logger.error("[adjust_camera] Missing channel layer or user ID. Cannot dispatch hardware command.")
                    result_msg = "Failed to send command: internal channel or auth error."
                
        except Exception as e:
            logger.error(f"[adjust_camera] Exception occurred during execution: {type(e).__name__} - {str(e)}", exc_info=True)
            result_msg = f"Error: {str(e)}"
            
        finally:
            if fc_id and self.session:
                try:
                    logger.info(f"[TOOL EXECUTION RETURN] Sending result back to Live API: '{result_msg}' for ID {fc_id}")
                    # Send tool response back to the live session
                    await self.session.send_tool_response(
                        function_responses=[
                            types.FunctionResponse(
                                id=fc_id,
                                name="adjust_camera",
                                response={"result": result_msg}
                            )
                        ]
                    )
                    logger.info("[TOOL EXECUTION END] tool_response successfully sent to Live API")
                except Exception as e:
                    logger.error(f"[adjust_camera] Error sending tool_response back to Voice API: {e}", exc_info=True)


