"""
Intelligent Conversation Manager
Demonstrates how AI agent conducts human-like conversations
with automatic data access and context awareness
"""

import logging
from typing import Dict, List, Any
from .gemini_service import get_gemini_service
from .enhanced_function_definitions import get_enhanced_tools_for_gemini
from .enhanced_function_executor import EnhancedFunctionExecutor

logger = logging.getLogger(__name__)


class IntelligentConversationManager:
    """
    Manages intelligent, human-like conversations with automatic context loading
    This is the BRAIN of the AI agent
    """
    
    def __init__(self, patient, user, session):
        self.patient = patient
        self.user = user
        self.session = session
        self.gemini = get_gemini_service()
        self.executor = EnhancedFunctionExecutor(patient, user)
        self.context = {}  # Loaded patient context
        self.conversation_history = []
    
    async def initialize_conversation(self, conversation_type: str = 'check_in'):
        """
        Initialize conversation by loading ALL relevant context
        This is called FIRST for any conversation (inbound/outbound)
        
        Makes AI truly intelligent and contextual!
        """
        logger.info(f"Initializing {conversation_type} conversation for {self.patient.user.get_full_name()}")
        
        # AUTOMATICALLY LOAD FULL CONTEXT
        # This is what makes the conversation intelligent!
        
        # 1. Get complete patient profile
        profile = self.executor.execute('get_complete_patient_profile', {})
        if profile.get('success'):
            self.context['patient'] = profile
        
        # 2. Get latest vitals
        vitals = self.executor.execute('get_latest_vital_readings', {'vital_type': 'all', 'count': 1})
        if vitals.get('success'):
            self.context['latest_vitals'] = vitals
        
        # 3. Get today's medications
        meds = self.executor.execute('get_todays_medication_schedule', {})
        if meds.get('success'):
            self.context['todays_medications'] = meds
        
        # 4. Get current alerts
        alerts = self.executor.execute('get_current_alerts', {})
        if alerts.get('success'):
            self.context['current_alerts'] = alerts
        
        # 5. Get recent conversation history
        history = self.executor.execute('get_conversation_history', {'days': 7, 'session_count': 3})
        if history.get('success'):
            self.context['previous_conversations'] = history
        
        # 6. Get any concerns
        concerns = self.executor.execute('get_patient_concerns', {})
        if concerns.get('success'):
            self.context['concerns'] = concerns
        
        logger.info(f"Context loaded: {list(self.context.keys())}")
        
        return self.context
    
    def build_patient_context(self) -> Dict[str, Any]:
        """
        Build comprehensive patient context for Gemini
        This is what makes the AI sound intelligent and informed
        """
        patient_info = self.context.get('patient', {}).get('patient_info', {})
        
        # Extract key information
        name = patient_info.get('preferred_name', patient_info.get('name', 'Patient'))
        age = patient_info.get('age')
        conditions = [c['condition_name'] for c in self.context.get('patient', {}).get('health_conditions', []) if isinstance(c, dict)]
        
        # Latest vitals summary
        latest_vitals = self.context.get('latest_vitals', {}).get('latest_readings', {})
        vitals_summary = []
        for code, data in latest_vitals.items():
            if data.get('readings'):
                latest = data['readings'][0]
                if code == 'BP':
                    vitals_summary.append(f"BP: {latest.get('systolic', '?')}/{latest.get('diastolic', '?')}")
                else:
                    vitals_summary.append(f"{data['name']}: {latest.get('value', '?')}")
        
        # Medication summary
        med_data = self.context.get('todays_medications', {})
        med_schedule = med_data.get('schedule', [])
        current_meds = list(set([m['medication_name'] for m in med_schedule]))
        
        med_summary = med_data.get('summary', {})
        total_meds = med_summary.get('total', 0)
        taken_meds = med_summary.get('taken', 0)
        
        # Alerts summary
        alert_data = self.context.get('current_alerts', {})
        critical_alerts = alert_data.get('counts', {}).get('critical', 0) + alert_data.get('counts', {}).get('emergency', 0)
        
        # Build context dict for Gemini
        context = {
            'name': name,
            'age': age,
            'conditions': conditions,
            'medications': current_meds,
            'latest_vitals_summary': vitals_summary,
            'medications_today': f"{taken_meds}/{total_meds} taken" if total_meds > 0 else "No medications scheduled",
            'has_critical_alerts': critical_alerts > 0,
            'previous_concerns': [c['concern'] for c in self.context.get('concerns', {}).get('concerns', [])]
        }
        
        return context
    
    async def start_conversation(self, initial_prompt: str = None):
        """
        Start the conversation with context-aware greeting
        This is what happens when AI calls patient or patient calls AI
        """
        # Ensure context is loaded if not already
        if not self.context:
            await self.initialize_conversation()

        patient_context = self.build_patient_context()
        
        # If no initial prompt, create intelligent greeting based on context
        if not initial_prompt:
            if patient_context.get('has_critical_alerts'):
                initial_prompt = "You noticed the patient has critical health alerts. Call to check on them with concern and empathy."
            elif patient_context.get('medications_today') and '0/' in patient_context['medications_today']:
                initial_prompt = "It's medication time. Gently remind the patient about their medications."
            else:
                initial_prompt = "Call the patient for a friendly daily health check-in. Ask how they're feeling today."
        
        # Get AI's initial response with FULL CONTEXT
        # Using sync call because gemini_service might be sync for now, await if it's async
        # Checking existing code... gemini_service.chat is sync.
        response = self.gemini.chat(
            message=initial_prompt,
            patient_context=patient_context,
            conversation_history=[],
            language=self.session.language,
            tools=get_enhanced_tools_for_gemini()
        )
        
        # Handle function calls if AI decides to call them
        if response.get('function_calls'):
            for fc in response['function_calls']:
                func_result = self.executor.execute(fc['name'], fc['parameters'])
                logger.info(f"AI called function: {fc['name']} -> {func_result}")
        
        # Save message
        self._save_message('AGENT', response['response_text'], response)
        
        return response['response_text']
    
    async def process_user_message(self, user_message: str):
        """
        Process user's message with full context awareness
        AI can automatically call functions to answer intelligently
        """
        # Save user message
        self._save_message('USER', user_message)
        
        # Build conversation history
        history = [
            {'sender': msg['sender'], 'content': msg['content']}
            for msg in self.conversation_history[-10:]  # Last 10 messages
        ]
        
        # Get patient context
        patient_context = self.build_patient_context()
        
        # Get AI response with tool calling
        response = self.gemini.chat(
            message=user_message,
            patient_context=patient_context,
            conversation_history=history,
            language=self.session.language,
            tools=get_enhanced_tools_for_gemini()
        )
        
        # Execute any function calls
        function_results = []
        if response.get('function_calls'):
            for fc in response['function_calls']:
                logger.info(f"AI calling function: {fc['name']} with params: {fc['parameters']}")
                func_result = self.executor.execute(fc['name'], fc['parameters'])
                function_results.append({
                    'function': fc['name'],
                    'result': func_result
                })
                
                # If function was successful, AI might reference the data in next response
                if func_result.get('success'):
                    # For data retrieval functions, add info to context
                    if fc['name'].startswith('get_'):
                        logger.info(f"Function {fc['name']} returned data for AI to use")
        
        # Save AI response
        self._save_message('AGENT', response['response_text'], {
            'tokens': response.get('output_tokens', 0),
            'function_calls': function_results
        })
        
        # Update session tokens
        self.session.input_tokens += response.get('input_tokens', 0)
        self.session.output_tokens += response.get('output_tokens', 0)
        self.session.save()
        
        return {
            'response': response['response_text'],
            'function_calls': function_results
        }
    
    def _save_message(self, sender: str, content: str, metadata: Dict = None):
        """Save message to database"""
        from .models import AgentMessage
        
        message = AgentMessage.objects.create(
            session=self.session,
            sender=sender,
            message_type='TEXT', # Default to TEXT, update if audio
            content=content,
            metadata=metadata or {}
        )
        
        # Also add to in-memory history
        self.conversation_history.append({
            'sender': sender,
            'content': content
        })
        
        return message
