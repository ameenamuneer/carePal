"""
CRITICAL FIX #1: Complete WebSocket Consumer
Replace backend/agent/consumers.py with this updated version
"""

import json
import logging
import uuid
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
    COMPLETE VERSION with IntelligentConversationManager integration
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            logger.warning("Unauthenticated connection attempt")
            await self.close()
            return
        
        # Get patient profile
        self.patient_profile = await self.get_patient_profile(self.user)
        if not self.patient_profile:
            logger.warning(f"User {self.user.id} has no patient profile")
            await self.close()
            return
        
        # Accept connection
        self.room_name = f"agent_user_{self.user.id}"
        await self.accept()
        
        # Create session
        self.session = await self.create_session()
        self.conversation_manager = None  # Will be created on first message
        
        logger.info(f"WebSocket connected for patient {self.patient_profile.id}")
        
        # Send connection confirmation
        await self.send_json({
            'type': 'connection',
            'status': 'connected',
            'session_id': self.session.session_id,
            'message': 'Connected to CarePAL AI Assistant'
        })
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'session'):
            await self.end_session()
        logger.info(f"WebSocket disconnected: {close_code}")
    
    async def receive(self, text_data):
        """
        Handle incoming messages
        COMPLETE IMPLEMENTATION with conversation manager
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'text')
            
            if message_type == 'text':
                user_message = data.get('message', '')
                
                if not user_message:
                    await self.send_json({
                        'type': 'error',
                        'message': 'Empty message received'
                    })
                    return
                
                # Create conversation manager on first message
                if not self.conversation_manager:
                    logger.info("Initializing conversation manager...")
                    
                    # Create manager
                    self.conversation_manager = await self.create_conversation_manager()
                    
                    # Initialize context (loads all patient data)
                    await self.conversation_manager.initialize_conversation()
                    
                    logger.info("Context initialized successfully")
                
                # Process message with intelligent conversation manager
                logger.info(f"Processing message: {user_message[:50]}...")
                
                result = await self.process_message_with_manager(user_message)
                
                # Send AI response
                await self.send_json({
                    'type': 'message',
                    'message': result['response'],
                    'sender': 'AGENT',
                    'timestamp': timezone.now().isoformat(),
                    'function_calls': result.get('function_calls', []),
                    'metadata': {
                        'session_id': self.session.session_id,
                        'tokens_used': result.get('tokens', 0)
                    }
                })
                
            elif message_type == 'audio':
                # Handle audio chunk (future enhancement)
                audio_data = data.get('audio')
                if audio_data:
                    await self.send_json({
                        'type': 'info',
                        'message': 'Audio processing coming soon'
                    })
                    
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Invalid message format'
            })
            
        except Exception as e:
            logger.error(f"Error in receive: {e}", exc_info=True)
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
        session = AgentSession.objects.create(
            patient=self.patient_profile,
            user=self.user,
            session_type='WEBSOCKET',
            status='ACTIVE',
            language=self.patient_profile.preferred_language or 'en'
        )
        logger.info(f"Created session: {session.session_id}")
        return session
    
    @database_sync_to_async
    def create_conversation_manager(self):
        """Create conversation manager instance"""
        return IntelligentConversationManager(
            patient=self.patient_profile,
            user=self.user,
            session=self.session
        )
    
    async def process_message_with_manager(self, user_message):
        """Process message using conversation manager"""
        # Use database_sync_to_async for the synchronous conversation manager
        @database_sync_to_async
        def _process():
            # Process message (this calls Gemini and executes functions)
            return self.conversation_manager.process_user_message(user_message)
        
        # Note: The conversation_manager.process_user_message is NOT async
        # so we need to wrap it
        # Actually, looking at the conversation_manager, it IS async
        # So we can call it directly
        
        result = await self.conversation_manager.process_user_message(user_message)
        return result
    
    @database_sync_to_async
    def end_session(self):
        """End current session"""
        if self.session:
            self.session.status = 'COMPLETED'
            self.session.ended_at = timezone.now()
            self.session.calculate_duration()
            self.session.calculate_cost()
            self.session.save()
            logger.info(f"Session ended: {self.session.session_id}")
