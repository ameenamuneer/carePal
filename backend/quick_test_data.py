import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from patients.models import PatientProfile
from vitals.models import VitalType, VitalReading
from medications.models import Medication
from medications.schedule_utils import default_dose_times_for_frequency

User = get_user_model()

def quick_setup():
    print("🚀 Quick Test Setup Starting...\n")
    
    # 1. User
    username = 'testuser_quick'
    user, _ = User.objects.get_or_create(username=username, defaults={'email': 'quick@test.com', 'is_active': True})
    user.set_password('Test@1234')
    user.save()
    print(f"✅ User: {username}")

    # 2. Patient Profile
    profile, _ = PatientProfile.objects.get_or_create(
        user=user,
        defaults={
            'gender': 'M', 'address_line1': '123 Test St', 'city': 'Test City',
            'state': 'TS', 'pincode': '12345'
        }
    )
    print("✅ Patient Profile")

    # 3. Vitals
    vt, _ = VitalType.objects.get_or_create(
        code='HR', 
        defaults={'name': 'Heart Rate', 'unit': 'bpm', 'category': 'CARDIOVASCULAR'}
    )
    
    for i in range(5):
        VitalReading.objects.create(
            patient=profile,
            vital_type=vt,
            value=70 + i,
            unit='bpm',
            measured_at=timezone.now() - timedelta(days=i)
        )
    print("✅ Vital Readings (HR)")

    # 4. Medications
    med = Medication.objects.create(
        patient=profile,
        medication_name='Aspirin',
        dosage='81mg',
        frequency='ONCE_DAILY',
        form='TABLET',
        route='ORAL',
        instructions='Daily',
        start_date=timezone.now().date(),
        status='ACTIVE'
    )
    
    if not med.dose_times:
        med.dose_times = default_dose_times_for_frequency(med.frequency)
        med.save(update_fields=['dose_times'])
    print("✅ Medication dose_times set")
    print("\nDONE.")

if __name__ == '__main__':
    quick_setup()
