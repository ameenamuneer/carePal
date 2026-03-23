
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
                            max_amp = torch.max(torch.abs(tensor)).item()
                            for i in range(0, len(tensor), 512):
                                chunk = tensor[i:i+512]
                                if len(chunk) < 512:
                                    continue # Skip trailing short chunks
                                speech_prob = self.vad_model(chunk, 16000).item()
                                if speech_prob > 0.5:
                                    is_speech = True
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
                                
                            # Fast interrupt check
                            if getattr(self, 'ai_is_speaking', False) and is_speech:
                                print("VAD detected speech while AI speaking. Triggering FAST INTERRUPT!", flush=True)
                                await self.send(bytes_data=bytes([0x03])) # Send 0x03 Interrupt binary to frontend immediately
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
- Proactively pan the camera to keep the user in center of the view or if the user is showing you something for eg: a medical device, a wound, etc.
- Use the 'move_camera' tool to adjust your view if needed.
- Use the 'record_vital_reading' tool to save health data.
- Considering that the user is in GMT +5:30, see if there are any medcations to be taked, and check if the user has taken the last medication when you get free time in the conversation..
"""

        # 3. Define Tools
        # Google GenAI SDK v1Beta/v2 format for tool definitions using types
        tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="move_camera",
                        description="Move the camera horizontally (pan). Use positive values for right, negative for left.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "pan_delta": types.Schema(
                                    type="INTEGER",
                                    description="Degrees to move (e.g. 10, -10, 45, -30 etc) negative means right, positive means left. the magnitude is in integer degrees."
                                )
                            },
                            required=["pan_delta"]
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
        )

        try:
            async with client.aio.live.connect(model=MODEL, config=config) as session:
                self.session = session
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
                            
                            server_content = getattr(response, "server_content", None)
                            if server_content:
                                logger.info(f"Server content: turn_complete={server_content.turn_complete}, interrupted={server_content.interrupted}")
                                if server_content.interrupted:
                                    logger.info("Gemini signaled interrupt. Sending 0x03 to frontend.")
                                    await self.send(bytes_data=bytes([0x03]))
                                    self.ai_is_speaking = False

                            # Handle Tool Calls
                            if response.tool_call:
                                logger.info(f"Received tool call: {response.tool_call}")
                                
                                async def process_tools(tool_call, current_session):
                                    function_responses = []
                                    for fc in tool_call.function_calls:
                                        fn_name = fc.name
                                        args = fc.args
                                        function_response_content = {}
                                        
                                        if fn_name == "move_camera":
                                            pan_delta = args.get("pan_delta", 0)
                                            payload = bytes([0x02]) + json.dumps({
                                                "type": "camera_control",
                                                "pan_delta": pan_delta
                                            }).encode('utf-8')
                                            await self.send(bytes_data=payload)
                                            function_response_content = {"result": "Camera movement command sent"}
                                            
                                        elif fn_name == "record_vital_reading":
                                            result = await self.save_vital_reading(
                                                vital_type_str=args.get("vital_type"),
                                                value=args.get("value"),
                                                systolic=args.get("systolic"),
                                                diastolic=args.get("diastolic")
                                            )
                                            function_response_content = result
                                        else:
                                            function_response_content = {"error": f"Unknown function {fn_name}"}

                                        function_responses.append(types.FunctionResponse(
                                            name=fn_name,
                                            id=fc.id,
                                            response=function_response_content
                                        ))

                                    if function_responses:
                                        tool_response = types.LiveClientToolResponse(function_responses=function_responses)
                                        await current_session.send(input=tool_response)
                                        
                                asyncio.create_task(process_tools(response.tool_call, session))

                            if response.data:
                                self.ai_is_speaking = True
                                payload = bytes([0x00]) + response.data
                                await self.send(bytes_data=payload)

                            if response.text:
                                logger.info(f"Received text: {response.text[:50]}...")
                                payload = bytes([0x02]) + json.dumps({
                                    "type": "text",
                                    "content": response.text
                                }).encode('utf-8')
                                await self.send(bytes_data=payload)
                        
                        logger.info("Receiver loop finished (turn complete). Re-entering...")
                        if self.stop_event.is_set():
                            break
                        
                        # Small delay to prevent busy looping if connection is dead but not raising error
                        await asyncio.sleep(0.05)

                except Exception as inner_e:
                    logger.error(f"Error inside receiver loop: {inner_e}", exc_info=True)
                    
                sender_task.cancel()

        except asyncio.CancelledError:
            logger.info("Gemini session cancelled")
            pass
        except Exception as e:
            logger.error(f"Gemini session error: {e}", exc_info=True)
            try:
                await self.send(text_data=json.dumps({"error": f"Gemini Error: {str(e)}"}))
            except:
                pass
        finally:
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

