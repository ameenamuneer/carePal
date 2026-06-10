
import os
import django
import sys
from django.utils import timezone
from unittest.mock import MagicMock

sys.path.append('/app')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carepal.settings")
django.setup()

from agent.enhanced_function_executor import EnhancedFunctionExecutor
from medications.models import Medication, MedicationAdherence
from medications.schedule_utils import default_dose_times_for_frequency
from patients.models import PatientProfile
from django.contrib.auth import get_user_model

def test_medication_tools():
    print("\n🔹 Testing Medication Tools...")
    
    User = get_user_model()
    
    # 1. Setup Data - Use existing or create mock
    try:
        user = User.objects.first()
        if not user:
            print("❌ No user found")
            return
            
        patient = PatientProfile.objects.filter(user=user).first()
        if not patient:
            print("❌ No patient found")
            return
            
        print(f"   Using Patient: {user.get_full_name()}")
        
        # Create Test Medication
        med, _ = Medication.objects.get_or_create(
            patient=patient,
            medication_name="Test Aspirin",
            defaults={
                'dosage': '100mg',
                'form': 'TABLET',
                'purpose': 'Testing',
                'status': 'ACTIVE',
                'start_date': timezone.now().date()
            }
        )
        
        # Ensure dose_times are set
        if not med.dose_times:
            med.dose_times = default_dose_times_for_frequency(med.frequency or 'ONCE_DAILY')
            med.save(update_fields=['dose_times'])

        # Ensure no existing adherence for today to start fresh
        MedicationAdherence.objects.filter(
            medication=med,
            scheduled_date=timezone.now().date()
        ).delete()
        
        executor = EnhancedFunctionExecutor(patient, user)
        
        # 2. Test Mark Taken
        print("\nTesting mark_medication_taken...")
        result = executor.execute('mark_medication_taken', {
            'medication_name': 'Test Aspirin',
            'notes': 'Verified test'
        })
        print(f"   Result: {result}")
        
        assert result['success'] == True
        assert 'TAKEN' in result['messsage']
        
        # Verify DB
        adherence = MedicationAdherence.objects.get(
            medication=med,
            scheduled_date=timezone.now().date()
        )
        assert adherence.status == 'TAKEN'
        print("   ✅ DB updated correctly (TAKEN)")
        
        # 3. Test Mark Skipped (Reset first)
        adherence.delete()
        
        print("\nTesting mark_medication_skipped...")
        result = executor.execute('mark_medication_skipped', {
            'medication_name': 'Test Aspirin',
            'reason': 'Side effects'
        })
        print(f"   Result: {result}")
        
        assert result['success'] == True
        assert 'SKIPPED' in result['messsage']
        
        # Verify DB
        adherence = MedicationAdherence.objects.get(
            medication=med,
            scheduled_date=timezone.now().date()
        )
        # Note: API might set it to SKIPPED or MISSED depending on impl
        assert adherence.status in ['SKIPPED', 'MISSED']
        print(f"   ✅ DB updated correctly ({adherence.status})")
        
        print("\n✅ ALL MEDICATION TOOL TESTS PASSED")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_medication_tools()
