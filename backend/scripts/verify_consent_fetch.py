
import os
import sys
import django
import logging
import json

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

from patients.models import PatientProfile
from abdm.services.eka_client import EKAClient

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_fetch_requests():
    try:
        # 1. Get Patient
        patient = PatientProfile.objects.get(id=7)
        print(f"👤 Patient: {patient.user.get_full_name()}")
        
        oid = getattr(patient, 'oid', None)
        print(f"🆔 OID: {oid}")

        # 2. Client
        client = EKAClient()

        # 3. Fetch Requests
        print("🔄 Fetching Consent Requests...")
        
        # Try fetching 'requested' (pending) consents
        response = client.get_patient_requests(
            status='requested', 
            type='consent-request', # OR 'CONSENT' depending on API docs, let's try standard
            oid=oid
        )

        print(f"✅ Response: {json.dumps(response, indent=2)}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    verify_fetch_requests()
