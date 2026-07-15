"""
Gemini 2.0 Flash AI Service
Handles all AI interactions with native audio support
"""

import os
import logging
import google.generativeai as genai
from django.conf import settings
from typing import Dict, List, Optional, Any
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Service for interacting with Gemini 2.0 Flash
    Supports text, audio, and function calling
    """
    
    def __init__(self):
        """Initialize Gemini with API key"""
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        
        # Use Gemini 2.0 Flash (cheaper than Pro, supports native audio)
        self.model = genai.GenerativeModel(
            'gemini-2.5-flash',
            generation_config=self._get_generation_config(),
            safety_settings=self._get_safety_settings()
        )
        
        logger.info("GeminiService initialized with gemini-2.5-flash")
    
    def _get_generation_config(self) -> dict:
        """Get generation configuration for consistent healthcare responses"""
        return {
            'temperature': 0.7,  # Balanced creativity and consistency
            'top_p': 0.9,
            'top_k': 40,
            'max_output_tokens': 2048,
        }
    
    def _get_safety_settings(self) -> list:
        """Get safety settings for healthcare context"""
        return [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
        ]
    
    def chat(
        self,
        message: str,
        patient_context: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        language: str = 'en',
        tools: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a text message to Gemini and get response
        
        Args:
            message: User's message
            patient_context: Relevant patient data
            conversation_history: Previous messages
            language: Language code
            tools: Function calling tools (optional)
        
        Returns:
            Dict with response, tokens, and function calls
        """
        try:
            # Build system instruction
            system_instruction = self._build_system_instruction(patient_context, language)
            
            # Build conversation
            messages = self._build_messages(conversation_history, message)
            
            # Create chat session
            chat = self.model.start_chat(
                history=messages[:-1] if len(messages) > 1 else []
            )
            
            # Send message
            if tools:
                response = chat.send_message(
                    messages[-1]['parts'][0],
                    tools=tools
                )
            else:
                response = chat.send_message(messages[-1]['parts'][0])
            
            # Parse response
            return self._parse_response(response)
        
        except Exception as e:
            logger.error(f"Error in Gemini chat: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response_text': "I apologize, I encountered an error. Please try again.",
                'input_tokens': 0,
                'output_tokens': 0,
                'function_calls': []
            }
    
    def chat_with_audio(
        self,
        audio_data: bytes,
        patient_context: Dict[str, Any],
        language: str = 'en',
        tools: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Process audio input with Gemini 2.0 Flash native audio
        
        Args:
            audio_data: Raw audio bytes
            patient_context: Patient context
            language: Language code
            tools: Function calling tools
        
        Returns:
            Dict with response and audio
        """
        try:
            # Build system instruction
            system_instruction = self._build_system_instruction(patient_context, language)
            
            # Create model with system instruction
            model_with_system = genai.GenerativeModel(
                'gemini-2.5-flash',
                generation_config=self._get_generation_config(),
                safety_settings=self._get_safety_settings(),
                system_instruction=system_instruction
            )
            
            # Process audio
            # Note: Gemini 2.0 Flash supports inline audio
            response = model_with_system.generate_content([
                {
                    "mime_type": "audio/wav",
                    "data": audio_data
                }
            ], tools=tools if tools else None)
            
            return self._parse_response(response, include_audio=True)
        
        except Exception as e:
            logger.error(f"Error in Gemini audio chat: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response_text': "I apologize, I encountered an error processing your audio.",
                'input_tokens': 0,
                'output_tokens': 0,
                'function_calls': []
            }
    
    def _build_system_instruction(self, patient_context: Dict[str, Any], language: str) -> str:
        """Build system instruction with patient context"""
        
        patient_name = patient_context.get('name', 'Patient')
        age = patient_context.get('age', 'Unknown')
        conditions = patient_context.get('conditions', [])
        medications = patient_context.get('medications', [])
        
        system_instruction = f"""You are CarePAL, a compassionate AI healthcare assistant for elderly patients and those with chronic illnesses in India.

PATIENT INFORMATION:
- Name: {patient_name}
- Age: {age} years
- Health Conditions: {', '.join(conditions) if conditions else 'None recorded'}
- Current Medications: {', '.join(medications) if medications else 'None recorded'}

YOUR ROLE:
1. Provide emotional support and companionship
2. Monitor patient wellbeing through conversation
3. Remind about medications
4. Detect concerning symptoms and create alerts
5. Answer health-related questions (within scope)
6. Assist with emergency situations

COMMUNICATION STYLE:
- Warm, patient, and respectful
- Use simple, clear language
- Be empathetic to elderly patients
- Respond in {self._get_language_name(language)}
- Ask one question at a time
- Keep responses concise (2-3 sentences typically)

IMPORTANT RULES:
- You are NOT a replacement for doctors
- Always encourage seeking medical help for serious concerns
- Use function calls to create alerts, record vitals, or notify family
- Be extra careful with symptoms suggesting emergency (chest pain, difficulty breathing, etc.)
- Maintain patient privacy and dignity

AVAILABLE FUNCTIONS:
You can call functions to:
- create_alert: Create health alerts
- record_vital_reading: Log vital sign readings
- get_medication_schedule: Check medication schedule
- call_emergency_contact: Initiate emergency call
- call_family_member: Call family member
- send_sms_notification: Send SMS alert
- log_patient_activity: Record patient activities
- get_patient_vitals_summary: Get recent vitals
- check_medication_adherence: Check medication compliance
- update_patient_notes: Add notes to patient record
- schedule_task: Schedule future tasks
- get_health_insights: Get AI health insights
- escalate_alert: Escalate existing alert

Respond naturally and use these functions when appropriate."""
        
        return system_instruction
    
    def _get_language_name(self, code: str) -> str:
        """Get full language name from code"""
        language_map = {
            'en': 'English',
            'hi': 'Hindi (हिंदी)',
            'ta': 'Tamil (தமிழ்)',
            'te': 'Telugu (తెలుగు)',
            'ml': 'Malayalam (മലയാളം)',
            'kn': 'Kannada (ಕನ್ನಡ)',
            'bn': 'Bengali (বাংলা)'
        }
        return language_map.get(code, 'English')
    
    def _build_messages(
        self,
        history: List[Dict[str, str]],
        current_message: str
    ) -> List[Dict]:
        """Build message list for Gemini"""
        messages = []
        
        # Add history
        for msg in history:
            role = 'user' if msg['sender'] == 'USER' else 'model'
            messages.append({
                'role': role,
                'parts': [msg['content']]
            })
        
        # Add current message
        messages.append({
            'role': 'user',
            'parts': [current_message]
        })
        
        return messages
    
    def _parse_response(self, response, include_audio: bool = False) -> Dict[str, Any]:
        """Parse Gemini response"""
        try:
            result = {
                'success': True,
                'response_text': response.text if hasattr(response, 'text') else '',
                'input_tokens': 0,  # Gemini doesn't always provide exact counts
                'output_tokens': 0,
                'function_calls': []
            }
            
            # Extract usage metadata if available
            if hasattr(response, 'usage_metadata'):
                result['input_tokens'] = getattr(response.usage_metadata, 'prompt_token_count', 0)
                result['output_tokens'] = getattr(response.usage_metadata, 'candidates_token_count', 0)
            
            # Extract function calls
            if hasattr(response, 'candidates'):
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call'):
                                fc = part.function_call
                                result['function_calls'].append({
                                    'name': fc.name,
                                    'parameters': dict(fc.args)
                                })
            
            # Extract audio if requested
            if include_audio and hasattr(response, 'candidates'):
                # Note: Audio extraction depends on Gemini's response format
                # This may need adjustment based on actual API behavior
                result['audio_available'] = True
            
            return result
        
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response_text': '',
                'input_tokens': 0,
                'output_tokens': 0,
                'function_calls': []
            }
    
    def generate_summary(self, conversation_history: List[Dict[str, str]]) -> str:
        """
        Generate a summary of conversation for context compression
        """
        try:
            messages_text = "\n".join([
                f"{msg['sender']}: {msg['content']}"
                for msg in conversation_history
            ])
            
            prompt = f"""Summarize this patient conversation in 2-3 sentences, focusing on key health information:

{messages_text}

Summary:"""
            
            response = self.model.generate_content(prompt)
            return response.text
        
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Unable to generate summary."
    
    def detect_language(self, text: str) -> str:
        """
        Detect language of input text
        Returns language code
        """
        try:
            prompt = f"""Detect the language of this text and respond with ONLY the language code (en, hi, ta, te, ml, kn, or bn):

Text: {text}

Language code:"""
            
            response = self.model.generate_content(prompt)
            detected = response.text.strip().lower()
            
            valid_codes = ['en', 'hi', 'ta', 'te', 'ml', 'kn', 'bn']
            return detected if detected in valid_codes else 'en'
        
        except Exception as e:
            logger.error(f"Error detecting language: {str(e)}")
            return 'en'
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text
        """
        try:
            # Gemini's count_tokens method
            result = self.model.count_tokens(text)
            return result.total_tokens
        except Exception as e:
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4


# Singleton instance
_gemini_service = None

def get_gemini_service() -> GeminiService:
    """Get or create GeminiService singleton"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
