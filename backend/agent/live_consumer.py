
import os
import json
import logging
import asyncio
import base64
from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types
from django.conf import settings

logger = logging.getLogger(__name__)

# Configure the model
MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

class GeminiLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.input_queue = asyncio.Queue()
        self.stop_event = asyncio.Event()
        self.session = None
        # Start the background task to manage Gemini connection
        self.task = asyncio.create_task(self.run_gemini_session())
        logger.info("Gemini Live WebSocket connected")

    async def disconnect(self, close_code):
        self.stop_event.set()
        if hasattr(self, 'task'):
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Gemini Live WebSocket disconnected")

    async def receive(self, text_data):
        """
        Receive message from WebSocket (Client)
        Expected format:
        {
            "type": "audio" | "image" | "text",
            "data": "base64_encoded_string", 
        "mime_type": "audio/pcm;rate=16000" (optional/required depending on type)
        }
        """
        try:
            data = json.loads(text_data)
            msg_type = data.get("type")
            
            if msg_type in ["audio", "image"]:
                # Construct the payload for Gemini
                # User snippet uses: {"mime_type": ..., "data": ...}
                payload = {
                    "mime_type": data.get("mime_type"),
                    "data": data.get("data")
                }
                await self.input_queue.put(payload)
            elif msg_type == "text":
                # For text, we might want to signal end of turn
                payload = data.get("data") # Just the text string
                # We might need to wrap it specifically or handle it in sender_loop
                # For now let's assume we pass it directly and handle logic in sender
                await self.input_queue.put({"text": payload})

        except Exception as e:
            logger.error(f"Error receiving data: {e}")

    async def run_gemini_session(self):
        api_key = os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None)
        
        if not api_key:
            logger.error("No Google API Key found")
            await self.send(text_data=json.dumps({"error": "No API Key"}))
            return

        client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=api_key,
        )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            media_resolution="MEDIA_RESOLUTION_MEDIUM",
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
            # Optional: context window compression
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=25600,
                sliding_window=types.SlidingWindow(target_tokens=12800),
            ),
        )

        try:
            async with client.aio.live.connect(model=MODEL, config=config) as session:
                self.session = session
                logger.info("Connected to Gemini Live")
                
                # Start the sender loop
                sender_task = asyncio.create_task(self.sender_loop())

                # Receiver loop
                async for response in session.receive():
                    if self.stop_event.is_set():
                        break

                    # Handle Audio
                    if response.data:
                        # raw PCM data
                        b64_audio = base64.b64encode(response.data).decode('utf-8')
                        await self.send(text_data=json.dumps({
                            "type": "audio",
                            "data": b64_audio
                        }))

                    # Handle Text (Transcript or response)
                    if response.text:
                        await self.send(text_data=json.dumps({
                            "type": "text",
                            "content": response.text
                        }))
                    
                    # Handle turn complete or other signals if needed

                sender_task.cancel()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Gemini session error: {e}")
            try:
                await self.send(text_data=json.dumps({"error": f"Gemini Error: {str(e)}"}))
            except:
                pass

    async def sender_loop(self):
        try:
            while True:
                item = await self.input_queue.get()
                
                if "text" in item:
                    # It's a text message
                    await self.session.send(input=item["text"], end_of_turn=True)
                else:
                    # It's media (audio/image) dict {"mime_type":..., "data":...}
                    await self.session.send(input=item)
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in sender loop: {e}")
