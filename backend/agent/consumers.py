"""
WebSocket Consumer for AI Agent
Handles real-time audio/text communication with intelligent context awareness
"""

import json
import logging
import base64
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import AgentSession, AgentMessage
from .conversation_manager import IntelligentConversationManager
from .gemini_service import get_gemini_service

logger = logging.getLogger(__name__)
User = get_user_model()

class AgentConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time AI interaction
    Supports:
    - Text chat
    - Real-time audio streaming (Twilio compatible)
    - Intelligent context loading
    - Function execution
    """
    
    async def connect(self):
        self.user = self.scope["user"]
        
        # Determine if this is a Twilio stream or Web Client
        # For authenticated web clients:
        if self.user.is_authenticated:
            self.room_name = f"agent_user_{self.user.id}"
            self.patient_profile = await self.get_patient_profile(self.user)
            if not self.patient_profile:
                logger.warning(f"User {self.user.id} has no patient profile")
                await self.close()
                return
        # For Twilio (unauthenticated, handled via stream ID later potentially, 
        # but for now assuming authenticated web client for this implementation phase)
        else:
             # Basic Auth or Twilio signature validation would happen here for production Twilio streams
             # For this scope, we focus on the Web/Flutter client authentication
             logger.warning("Unauthenticated connection attempt")
             await self.close()
             return

        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        await self.accept()
        
        # Initialize Session
        self.session = await self.create_session()
        
        # Initialize Conversation Manager
        self.manager = IntelligentConversationManager(
            self.patient_profile, 
            self.user, 
            self.session
        )
        
        # Load Context
        await self.manager.initialize_conversation()
        
        # Send initial greeting
        greeting = await self.manager.start_conversation()
        await self.send_json({
            'type': 'text',
            'content': greeting,
            'sender': 'AGENT'
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'session'):
            await self.end_session()
            
        if hasattr(self, 'room_name'):
            await self.channel_layer.group_discard(
                self.room_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'text')
            
            if message_type == 'text':
                content = data.get('content')
                if content:
                    # Process message via Manager
                    result = await self.manager.process_user_message(content)
                    
                    # Send response back
                    await self.send_json({
                        'type': 'text',
                        'content': result['response'],
                        'sender': 'AGENT',
                        'function_calls': result.get('function_calls')
                    })
                    
            elif message_type == 'audio':
                # Handle audio chunk
                audio_data = data.get('audio') # Base64 encoded
                if audio_data:
                    # For future: Stream to Gemini Audio
                    pass
                
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Error processing message'
            })

    async def send_json(self, content):
        """Helper to send JSON response"""
        await self.send(text_data=json.dumps(content))

    @database_sync_to_async
    def get_patient_profile(self, user):
        """Get patient profile safely"""
        if hasattr(user, 'patient_profile'):
            return user.patient_profile
        return None

    @database_sync_to_async
    def create_session(self):
        """Create new agent session"""
        return AgentSession.objects.create(
            patient=self.patient_profile,
            started_at=timezone.now(),
            status='ACTIVE',
            session_type='CHAT', # or VOICE
            language=self.patient_profile.preferred_language or 'en'
        )

    @database_sync_to_async
    def end_session(self):
        """End current session"""
        if self.session:
            self.session.status = 'COMPLETED'
            self.session.ended_at = timezone.now()
            self.session.save()
            
            # Generate summary logic could go here
            # summary = get_gemini_service().generate_summary(...)
            # self.session.summary = summary
            # self.session.save()
