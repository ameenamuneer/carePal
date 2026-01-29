# backend/agent/voice_consumers.py

"""
Voice WebSocket Consumer
========================

Integrates with existing agent/consumers.py
Add these methods to the existing PatientWebSocketConsumer
"""

import json
import base64
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .gemini_live_voice_service import LiveVoiceConversationHandler

logger = logging.getLogger(__name__)


class VoiceEnabledConsumerMixin:
    """
    Add this mixin to existing PatientWebSocketConsumer
    
    Update in backend/agent/consumers.py:
    
    class AgentConsumer(AsyncWebsocketConsumer, VoiceEnabledConsumerMixin):
        ...
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_handler = None
    
    async def handle_voice_start_conversation(self, data: dict):
        """
        Handle voice conversation start request
        
        Message from Flutter:
        {
            'type': 'voice.start_conversation',
            'adherence_id': 123,  // Optional
            'language': 'en'
        }
        """
        try:
            # We assume self.user and self.patient_profile are set by the main consumer
            # self.patient_profile should be available from connect method of AgentConsumer
            if not hasattr(self, 'patient_profile') or not self.patient_profile:
                 logger.error("[VOICE-WS] Patient profile not found on consumer instance")
                 await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Patient profile not found. Please reconnect.'
                }))
                 return

            adherence_id = data.get('adherence_id')
            language = data.get('language', 'en')
            mime_type = data.get('mime_type', 'audio/pcm')
            
            # Initialize voice handler
            self.voice_handler = LiveVoiceConversationHandler(
                patient_id=self.patient_profile.id
            )
            
            # Start conversation
            if adherence_id:
                result = await self.voice_handler.start_medication_reminder(
                    adherence_id=adherence_id,
                    language=language,
                    mime_type=mime_type
                )
            else:
                # General conversation
                result = await self.voice_handler.start_general_conversation(
                    language=language,
                    mime_type=mime_type
                )
            
            # Send confirmation to frontend
            await self.send(text_data=json.dumps({
                'type': 'voice_conversation_started',
                'session_id': result['session_id'],
                'status': result['status'],
                'timestamp': timezone.now().isoformat()
            }))
            
            logger.info(
                f"[VOICE-WS] Started conversation for patient {self.patient_profile.id}, "
                f"session: {result['session_id']}"
            )
            
        except Exception as e:
            logger.error(f"[VOICE-WS] Error starting conversation: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to start conversation: {str(e)}'
            }))
    
    async def handle_voice_audio_input(self, data: dict):
        """
        Handle audio input from patient's microphone
        
        Message from Flutter:
        {
            'type': 'voice.audio',
            'audio': 'base64_encoded_audio_chunk',
            'session_id': 'session_123'
        }
        """
        try:
            if not self.voice_handler:
                logger.warning("[VOICE-WS] No active voice session")
                return
            
            # Decode audio
            audio_b64 = data.get('audio', '')
            if not audio_b64:
                return

            try:
                audio_bytes = base64.b64decode(audio_b64)
            except Exception as e:
                logger.error(f"[VOICE-WS] Base64 decode error: {e}")
                return
            
            # Send to Gemini
            await self.voice_handler.process_patient_audio(audio_bytes)
            
        except Exception as e:
            logger.error(f"[VOICE-WS] Error processing audio: {e}")
    
    async def handle_voice_stop(self, data: dict):
        """
        Handle stop conversation request
        
        Message from Flutter:
        {
            'type': 'voice.stop'
        }
        """
        try:
            if self.voice_handler:
                await self.voice_handler.stop()
                self.voice_handler = None
            
            await self.send(text_data=json.dumps({
                'type': 'voice_conversation_stopped',
                'timestamp': timezone.now().isoformat()
            }))
            
            logger.info(f"[VOICE-WS] Stopped conversation for patient {getattr(self, 'patient_profile', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"[VOICE-WS] Error stopping conversation: {e}")
    
    # ==================== OUTGOING MESSAGES ====================
    # These handlers are called by channel layers group_send
    
    async def voice_audio_output(self, event):
        """
        Send AI audio to patient's speaker
        
        Called by voice_stream_service when AI speaks
        """
        await self.send(text_data=json.dumps({
            'type': 'voice_audio_output',
            'audio_data': event['audio_data'],
            'session_id': event.get('session_id'),
            'timestamp': event.get('timestamp')
        }))
    
    async def voice_transcript(self, event):
        """
        Send conversation transcript update
        
        For real-time transcript display in UI
        """
        await self.send(text_data=json.dumps({
            'type': 'voice_transcript',
            'sender': event['sender'],
            'text': event['text'],
            'timestamp': event.get('timestamp')
        }))
