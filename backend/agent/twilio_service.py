"""
Twilio Service
Handles phone calls and SMS via Twilio API
"""

import logging
from typing import Dict, Any, Optional
from django.conf import settings
import os

logger = logging.getLogger(__name__)

# Twilio imports (will need to add to requirements.txt)
try:
    from twilio.rest import Client
    from twilio.twiml.voice_response import VoiceResponse, Gather
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("Twilio library not installed. Install with: pip install twilio")


class TwilioService:
    """
    Service for Twilio voice calls and SMS
    """
    
    def __init__(self):
        """Initialize Twilio client"""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID', getattr(settings, 'TWILIO_ACCOUNT_SID', ''))
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN', getattr(settings, 'TWILIO_AUTH_TOKEN', ''))
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER', getattr(settings, 'TWILIO_PHONE_NUMBER', ''))
        
        if TWILIO_AVAILABLE and self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
            self.enabled = True
            logger.info("TwilioService initialized successfully")
        else:
            self.client = None
            self.enabled = False
            logger.warning("TwilioService not enabled - missing credentials or library")
    
    def is_enabled(self) -> bool:
        """Check if Twilio is enabled"""
        return self.enabled
    
    def initiate_emergency_call(
        self,
        to_number: str,
        patient_name: str,
        reason: str,
        urgency: str
    ) -> Dict[str, Any]:
        """
        Initiate emergency call to contact
        
        Args:
            to_number: Phone number to call
            patient_name: Patient's name
            reason: Reason for emergency
            urgency: HIGH or CRITICAL
        
        Returns:
            Dict with call details
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Twilio service not enabled'
            }
        
        try:
            # Create TwiML for the call
            twiml = self._generate_emergency_twiml(patient_name, reason, urgency)
            
            # Initiate call
            call = self.client.calls.create(
                twiml=twiml,
                to=to_number,
                from_=self.phone_number,
                status_callback=f"{settings.get('BASE_URL', '')}/api/v1/agent/twilio/status/",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                record=True  # Record the call for documentation
            )
            
            logger.info(f"Emergency call initiated: {call.sid} to {to_number}")
            
            return {
                'success': True,
                'call_sid': call.sid,
                'to_number': to_number,
                'status': call.status
            }
        
        except Exception as e:
            logger.error(f"Error initiating emergency call: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def initiate_family_call(
        self,
        to_number: str,
        patient_name: str,
        reason: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Initiate call to family member
        
        Args:
            to_number: Phone number to call
            patient_name: Patient's name
            reason: Reason for call
            message: Message to convey
        
        Returns:
            Dict with call details
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Twilio service not enabled'
            }
        
        try:
            # Create TwiML
            twiml = self._generate_family_call_twiml(patient_name, reason, message)
            
            # Initiate call
            call = self.client.calls.create(
                twiml=twiml,
                to=to_number,
                from_=self.phone_number,
                status_callback=f"{settings.get('BASE_URL', '')}/api/v1/agent/twilio/status/",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed']
            )
            
            logger.info(f"Family call initiated: {call.sid} to {to_number}")
            
            return {
                'success': True,
                'call_sid': call.sid,
                'to_number': to_number,
                'status': call.status
            }
        
        except Exception as e:
            logger.error(f"Error initiating family call: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_sms(
        self,
        to_number: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send SMS message
        
        Args:
            to_number: Phone number
            message: SMS message
        
        Returns:
            Dict with message details
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Twilio service not enabled'
            }
        
        try:
            # Send SMS
            message_obj = self.client.messages.create(
                body=message,
                to=to_number,
                from_=self.phone_number,
                status_callback=f"{settings.get('BASE_URL', '')}/api/v1/agent/twilio/sms-status/"
            )
            
            logger.info(f"SMS sent: {message_obj.sid} to {to_number}")
            
            return {
                'success': True,
                'message_sid': message_obj.sid,
                'to_number': to_number,
                'status': message_obj.status
            }
        
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_emergency_twiml(
        self,
        patient_name: str,
        reason: str,
        urgency: str
    ) -> str:
        """Generate TwiML for emergency call"""
        response = VoiceResponse()
        
        urgency_text = "CRITICAL EMERGENCY" if urgency == "CRITICAL" else "URGENT ALERT"
        
        # Initial message
        response.say(
            f"{urgency_text} from CarePAL Healthcare System. "
            f"This is regarding {patient_name}. "
            f"Reason: {reason}. "
            f"Please check on the patient immediately. "
            f"Press 1 to acknowledge this alert, or press 2 to speak with the AI assistant.",
            voice='alice',
            language='en-IN'
        )
        
        # Gather response
        gather = Gather(
            num_digits=1,
            action=f"{settings.get('BASE_URL', '')}/api/v1/agent/twilio/handle-emergency/",
            method='POST',
            timeout=10
        )
        response.append(gather)
        
        # If no input, repeat
        response.say(
            "No response received. Please press 1 to acknowledge or 2 for assistance.",
            voice='alice',
            language='en-IN'
        )
        response.redirect(f"{settings.get('BASE_URL', '')}/api/v1/agent/twilio/emergency-repeat/")
        
        return str(response)
    
    def _generate_family_call_twiml(
        self,
        patient_name: str,
        reason: str,
        message: str
    ) -> str:
        """Generate TwiML for family call"""
        response = VoiceResponse()
        
        response.say(
            f"Hello, this is CarePAL calling about {patient_name}. "
            f"{message}. "
            f"Press 1 to acknowledge this message.",
            voice='alice',
            language='en-IN'
        )
        
        gather = Gather(
            num_digits=1,
            action=f"{settings.get('BASE_URL', '')}/api/v1/agent/twilio/handle-family/",
            method='POST',
            timeout=10
        )
        response.append(gather)
        
        return str(response)
    
    def handle_emergency_response(self, digit: str, call_sid: str) -> str:
        """
        Handle response from emergency call
        
        Args:
            digit: Digit pressed (1 or 2)
            call_sid: Twilio call SID
        
        Returns:
            TwiML response
        """
        response = VoiceResponse()
        
        if digit == '1':
            # Acknowledged
            response.say(
                "Thank you for acknowledging. Please check on the patient immediately.",
                voice='alice',
                language='en-IN'
            )
            response.hangup()
        elif digit == '2':
            # Connect to AI assistant (future feature)
            response.say(
                "Connecting you to the AI assistant.",
                voice='alice',
                language='en-IN'
            )
            # TODO: Implement live agent connection
            response.hangup()
        else:
            response.say(
                "Invalid input. Goodbye.",
                voice='alice',
                language='en-IN'
            )
            response.hangup()
        
        return str(response)
    
    def initiate_patient_call(
        self,
        to_number: str,
        patient_name: str,
        session_id: str,
        websocket_url: str
    ) -> Dict[str, Any]:
        """
        Initiate AI voice call to patient
        Uses Twilio Streams for real-time audio to WebSocket
        
        Args:
            to_number: Patient's phone number
            patient_name: Patient's name
            session_id: Agent session ID
            websocket_url: WebSocket URL for audio streaming
        
        Returns:
            Dict with call details
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Twilio service not enabled'
            }
        
        try:
            # Create TwiML with Stream
            response = VoiceResponse()
            response.say(
                f"Hello {patient_name}, this is CarePAL, your health assistant. How are you feeling today?",
                voice='alice',
                language='en-IN'
            )
            
            # Start media stream to WebSocket
            start = response.start()
            start.stream(
                url=websocket_url,
                track='both_tracks'  # Inbound and outbound audio
            )
            
            # Keep call alive for conversation
            response.pause(length=60)
            
            # Initiate call
            call = self.client.calls.create(
                twiml=str(response),
                to=to_number,
                from_=self.phone_number,
                status_callback=f"{settings.get('BASE_URL', '')}/api/v1/agent/twilio/status/",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                record=True
            )
            
            logger.info(f"Patient AI call initiated: {call.sid} to {to_number}")
            
            return {
                'success': True,
                'call_sid': call.sid,
                'to_number': to_number,
                'session_id': session_id,
                'status': call.status
            }
        
        except Exception as e:
            logger.error(f"Error initiating patient call: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
_twilio_service = None

def get_twilio_service() -> TwilioService:
    """Get or create TwilioService singleton"""
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioService()
    return _twilio_service
