
import os
import sys
import django
import uuid
import logging

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

from patients.models import PatientProfile
from abdm.services.eka_client import EKAClient

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_link_init():
    try:
        # 1. Get Patient
        patient = PatientProfile.objects.get(id=7)
        mobile = patient.user.phone_number
        if not mobile:
            print("❌ Patient has no mobile number")
            return

        print(f"👤 Patient: {patient.user.get_full_name()} ({mobile})")
        
        # 2. Context ID
        context_id = f"vitals-{patient.id}"
        print(f"🏥 Check Context: {context_id}")

        # 3. Client
        client = EKAClient()

        # 4. Initiate Link
        txn_id = str(uuid.uuid4())
        print(f"🔄 Initiating Link Request (Txn: {txn_id})...")
        
        # Note: 'patient_ref_id' usually matches 'ref_id' used in discovery, which is often mobile or patient ID.
        # Let's try sending mobile.
        response = client.initiate_link_care_contexts(
            txn_id=txn_id,
            patient_ref_id=mobile,
            cc_ref_id=context_id
        )

        print(f"✅ Response: {response}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    verify_link_init()
