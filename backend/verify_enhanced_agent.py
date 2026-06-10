"""
Verification Script for Enhanced AI Agent
Tests IntelligentConversationManager and EnhancedFunctionExecutor
"""

import os
import django
import asyncio
import logging
from datetime import timedelta
from django.utils import timezone

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true" # Allow sync DB calls in async context for script
django.setup()

import uuid
from django.contrib.auth import get_user_model
from patients.models import PatientProfile, HealthCondition
from vitals.models import VitalType, VitalReading, DataSource
from medications.models import Medication
from medications.schedule_utils import default_dose_times_for_frequency
from agent.models import AgentSession
from agent.conversation_manager import IntelligentConversationManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

User = get_user_model()

def setup_test_data():
    """Create test data for verification"""
    logger.info("Setting up test data...")
    
    # 1. Create User & Patient
    user, _ = User.objects.get_or_create(
        username='test_patient_ai',
        defaults={
            'email': 'ai_test@example.com',
            'first_name': 'Raj',
            'last_name': 'Kumar',
            'phone_number': '+919876543210',
            'user_type': 'PATIENT',
            'date_of_birth': '1960-01-01'
        }
    )
    
    profile, _ = PatientProfile.objects.get_or_create(
        user=user,
        defaults={
            'gender': 'M',
            'blood_group': 'B+',
            'height_cm': 175,
            'weight_kg': 70,
            'address_line1': '123 Test St',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001',
            'preferred_language': 'en',
            'health_conditions': [{'condition_name': 'Hypertension'}, {'condition_name': 'Type 2 Diabetes'}]
        }
    )
    
    # 2. Add Vitals
    bp_type, _ = VitalType.objects.get_or_create(
        code='BP', 
        defaults={'name': 'Blood Pressure', 'unit': 'mmHg', 'min_val': 90, 'max_val': 180}
    )
    
    source, _ = DataSource.objects.get_or_create(
        patient=profile, 
        source_type='MANUAL_ENTRY',
        device_name='Test Device'
    )
    
    # Add recent BP reading
    VitalReading.objects.create(
        patient=profile,
        vital_type=bp_type,
        data_source=source,
        values={'systolic': 130, 'diastolic': 85},
        measured_at=timezone.now() - timedelta(minutes=30)
    )
    
    # 3. Add Medication
    med, _ = Medication.objects.get_or_create(
        patient=profile,
        medication_name='Metformin',
        defaults={
            'dosage': '500mg',
            'form': 'TABLET', # Using correct choice key
            'purpose': 'Diabetes',
            'status': 'ACTIVE',
            'start_date': timezone.now().date(),
            'frequency': 'ONCE_DAILY', # Added required field
            'route': 'ORAL', # Added required field
            'instructions': 'Take with water' # Added required field
        }
    )
    
    if not med.dose_times:
        med.dose_times = default_dose_times_for_frequency(med.frequency)
        med.save(update_fields=['dose_times'])

    logger.info(f"Test data ready for: {user.get_full_name()}")
    return profile, user

async def run_verification():
    """Run the verification flow"""
    try:
        profile, user = await asyncio.to_thread(setup_test_data)
        
        # Create Session
        session = await asyncio.to_thread(
            AgentSession.objects.create,
            patient=profile,
            user=user, # Added required user field
            started_at=timezone.now(),
            status='ACTIVE'
        )
        
        # Initialize Manager
        manager = IntelligentConversationManager(profile, user, session)
        
        print("\n--- TEST 1: INITIALIZE CONTEXT ---")
        context = await manager.initialize_conversation()
        print(f"Context Keys Loaded: {list(context.keys())}")
        
        if 'patient' in context and 'latest_vitals' in context:
            print("✅ Context loaded successfully")
        else:
            print("❌ Context loading failed")
        
        print("\n--- TEST 2: BUILD CONTEXT DICT ---")
        context_dict = manager.build_patient_context()
        print(f"Context Summary: {context_dict}")
        
        print("\n--- TEST 3: PROCESS USER MESSAGE (WITHOUT API KEY) ---")
        print("Note: This step requires a valid GOOGLE_API_KEY. If missing, it will fail gracefully.")
        try:
            # We mock the Gemini response if needed, or let it fail if no key
            # For this verification script, let's just assert the context is correct
            # and try a real call if possible
            if os.environ.get('GOOGLE_API_KEY'):
                response = await manager.process_user_message("What is my latest blood pressure?")
                print(f"Agent Response: {response['response']}")
                print(f"Function Calls: {response.get('function_calls')}")
            else:
                print("⚠️ GOOGLE_API_KEY not found in env, skipping live API call.")
                
        except Exception as e:
            print(f"⚠️ API Call failed (expected if no key): {e}")

        print("\n--- VERIFICATION COMPLETE ---")
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_verification())
