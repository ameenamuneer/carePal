import os
import django
import sys
from datetime import timedelta
from django.utils import timezone

# Add backend to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

from django.contrib.auth import get_user_model
from patients.models import PatientProfile
from vitals.models import VitalType, VitalReading
from medications.models import Medication
from analytics.engines.metrics_engine import MetricsEngine

User = get_user_model()

def check_backend():
    print("🔍 Backend Health Check (Adapted)\n")
    print("="*60)
    
    # Check database connection
    try:
        user_count = User.objects.count()
        print(f"✅ Database connected - {user_count} users found")
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    # Check if test user exists
    target_username = 'test_patient'
    try:
        test_user = User.objects.filter(username=target_username).first()
        if test_user:
            print(f"✅ Test user exists: {target_username}")
            
            # Check patient
            patient = PatientProfile.objects.filter(user=test_user).first()
            if patient:
                print(f"✅ Patient profile exists for {patient.user.get_full_name()}")
                
                # Check vitals
                vital_count = VitalReading.objects.filter(patient=patient).count()
                print(f"✅ Vital readings: {vital_count}")
                
                # Check medications
                med_count = Medication.objects.filter(patient=patient).count()
                print(f"✅ Medications: {med_count}")
                
                # Test dashboard generation logic (MetricsEngine)
                try:
                    end_date = timezone.now().date()
                    start_date = end_date - timedelta(days=7)
                    engine = MetricsEngine(patient)
                    metrics = engine.compute_period_metrics(start_date, end_date)
                    
                    print(f"✅ Metrics Engine working")
                    print(f"   - Health Score: {metrics['overall']['health_score']}")
                    print(f"   - Vitals Summary: {len(metrics['vitals'])} types tracked")
                except Exception as e:
                    print(f"❌ Metrics Engine error: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"⚠️  No patient profile for {target_username}")
        else:
            print(f"⚠️  Test user '{target_username}' not found")
            print(f"   Run: python quick_test_data.py")
    except Exception as e:
        print(f"❌ Error checking test user: {e}")
        import traceback
        traceback.print_exc()
    
    # Check vital types
    try:
        vital_types = VitalType.objects.all()
        print(f"✅ Vital types: {vital_types.count()}")
        for vt in vital_types:
            print(f"   - {vt.code}: {vt.name}")
    except Exception as e:
        print(f"❌ Vital types error: {e}")
    
    # Check API endpoints exist
    print("\n" + "="*60)
    print("📡 Checking API Endpoints...")
    print("="*60)
    
    endpoints = [
        '/api/v1/auth/login/',
        '/api/v1/auth/register/',
        '/api/v1/analytics/dashboard/patient/',
        '/api/v1/vitals/readings/',
        '/api/v1/vitals/types/',
        '/api/v1/medications/adherence/today/',
    ]
    
    from django.urls import resolve
    from django.urls.exceptions import Resolver404
    
    for endpoint in endpoints:
        try:
            resolve(endpoint)
            print(f"✅ {endpoint}")
        except Resolver404:
            print(f"❌ {endpoint} - NOT FOUND")
    
    print("\n" + "="*60)
    print("✅ Backend check complete!")
    print("="*60)
    
    return True

if __name__ == '__main__':
    check_backend()
