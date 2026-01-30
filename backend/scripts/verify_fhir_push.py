import os
import sys
import django
from datetime import datetime
import json

# Setup Django Environment
# Add the project root (backend/) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

from users.models import User
from patients.models import PatientProfile
from vitals.models import VitalReading, VitalType
from abdm.models import ABHAProfile, CareContext

def verify_push():
    print("🚀 Starting ABHA Data Push Verification...")
    
    # 1. Get or Create User & Patient
    print("\n1️⃣  Setting up Test Patient...")
    user, _ = User.objects.get_or_create(
        email='test_abha@example.com',
        defaults={
            'username': 'test_abha',
            'first_name': 'Abha',
            'last_name': 'Tester',
            'phone_number': '9999999999',
            'user_type': 'PATIENT'
        }
    )
    patient, _ = PatientProfile.objects.get_or_create(user=user)
    print(f"   ✅ Patient: {user.get_full_name()}")

    # 2. Link Mock ABHA Profile
    print("\n2️⃣  Linking Mock ABHA Profile...")
    abha_profile, created = ABHAProfile.objects.get_or_create(
        patient=patient,
        defaults={
            'abha_address': 'test_user@abdm',
            'abha_number': '99-9999-9999-9999',
            'full_name': 'Abha Tester', # Corrected field name from 'name' to 'full_name'
            'gender': 'M',
            'mobile': '9999999999'
        }
    )
    if created:
        print("   ✅ Created new ABHA Profile linkage")
    else:
        print("   ✅ Found existing ABHA linkage")

    # 3. Create Vital Type (Heart Rate)
    print("\n3️⃣  Ensuring Vital Type 'Heart Rate' exists...")
    hr_type, _ = VitalType.objects.get_or_create(
        code='HR',
        defaults={
            'name': 'Heart Rate',
            'category': 'CARDIOVASCULAR',
            'unit': 'bpm',
            'is_continuous': True
        }
    )
    print(f"   ✅ Vital Type: {hr_type}")

    # 4. Simulate a Reading (Triggering the Signal)
    print("\n4️⃣  Saving Vital Reading (Triggering Signal)...")
    # Note: The actual logging happens in the signal, so we watch stdout
    reading = VitalReading.objects.create(
        patient=patient,
        vital_type=hr_type,
        value=72,
        unit='bpm',
        measured_at=datetime.now(),
        notes="Test reading for ABHA Push"
    )
    print(f"   ✅ Saved Reading ID: {reading.id} (Value: 72 bpm)")
    
    # 5. Verify Care Context Creation
    print("\n5️⃣  Verifying Care Context...")
    ctx_id = f"vitals-{patient.id}"
    try:
        context = CareContext.objects.get(context_id=ctx_id)
        print(f"   ✅ Care Context Found: {context.display_name} ({context.context_id})")
        print(f"   ✅ Linked Status: {context.is_linked}")
    except CareContext.DoesNotExist:
        print(f"   ❌ Care Context {ctx_id} was NOT created!")

    print("\n✨ Verification Complete. Check logs above for '📦 [FHIR GENERATED]'.")

if __name__ == '__main__':
    verify_push()
