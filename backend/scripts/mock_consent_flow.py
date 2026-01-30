
import os
import sys
import django
import logging
import json
import uuid
from datetime import timedelta
from django.utils import timezone
from unittest.mock import MagicMock, patch

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

from patients.models import PatientProfile
from abdm.models import ABHAProfile, CareContext, ConsentRequest
from abdm.services.eka_client import EKAClient
from abdm.views import approve_consent_view
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def mock_consent_simulation():
    print("🚀 Starting Consent Approval Simulation...")
    
    # 1. Setup Data
    try:
        patient = PatientProfile.objects.get(id=7)
        abha_profile = patient.abha_profile
        
        # Ensure a Care Context exists
        context, _ = CareContext.objects.get_or_create(
            patient=patient,
            context_id=f"vitals-{patient.id}",
            defaults={
                'abha_profile': abha_profile,
                'context_type': 'vitals',
                'display_name': 'Vital Signs',
                'from_date': timezone.now().date(),
                'to_date': timezone.now().date()
            }
        )
        print(f"✅ Context Ready: {context.context_id}")

        # 2. Create MOCK Pending Request
        consent_id = str(uuid.uuid4())
        req = ConsentRequest.objects.create(
            abha_profile=abha_profile,
            consent_id=consent_id,
            consent_request_id=str(uuid.uuid4()),
            requester_name="Dr. Test (Simulation)",
            requester_id="DOC-101",
            purpose="Care Management",
            from_date=timezone.now().date(),
            to_date=timezone.now().date(),
            expires_at=timezone.now() + timedelta(days=7),
            status='pending'
        )
        print(f"✅ Created Mock Request: {consent_id}")

        # 3. Simulate Approval Payload (Frontend sends this)
        payload = {
            'id': consent_id,
            'consent_artefacts': [
                {
                   'hip_id': 'CAREPAL_HEALTH', # Our ID
                   'care_contexts': [
                       {'id': context.context_id, 'display': context.display_name}
                   ],
                   'hi_types': ['HealthDocumentRecord'],
                   'access_mode': 'view',
                   'duration': {
                       'from': '2023-01-01T00:00:00Z',
                       'to': '2023-12-31T23:59:59Z'
                   },
                   'erase_at': '2026-01-01T00:00:00Z'
                }
            ]
        }

        # 4. Intercept the EKA Client Call
        # We want to see what is sent to the network
        with patch('abdm.services.eka_client.EKAClient._make_request') as mock_post:
            mock_post.return_value = {'status': 'success'}
            
            # Initialize Client
            client = EKAClient()
            
            print("🔄 Triggering Approval...")
            client.approve_consent_request(payload, oid=None)
            
            # 5. Verify the Outgoing Payload
            args, kwargs = mock_post.call_args
            sent_url = args[1]
            sent_data = kwargs['data']
            
            print("\n🔍 --- VERIFICATION ---")
            if sent_url == '/abdm/v1/consents/approve':
                print("✅ 1. Endpoint Correct: /abdm/v1/consents/approve")
            else:
                print(f"❌ 1. Wrong Endpoint: {sent_url}")
                
            artefacts = sent_data.get('consent_artefacts', [])
            if artefacts and len(artefacts) > 0:
                print(f"✅ 2. Artefacts Generated: {len(artefacts)}")
                ctx = artefacts[0].get('care_contexts', [])[0]
                if ctx['id'] == f"vitals-{patient.id}":
                    print(f"✅ 3. Correct Context Included: {ctx['id']}")
                else:
                    print(f"❌ 3. Wrong Context: {ctx}")
            else:
                print("❌ 2. No Artefacts found in payload!")

            print(f"\n📦 Full Payload Sent to ABHA:\n{json.dumps(sent_data, indent=2)}")

    except Exception as e:
        print(f"❌ Simulation Failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    mock_consent_simulation()
