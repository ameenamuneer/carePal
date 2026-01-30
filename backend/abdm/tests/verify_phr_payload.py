
import os
import django
from django.conf import settings
import sys
from unittest.mock import MagicMock, patch

# setup django
sys.path.append('/app')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carepal.settings")
django.setup()

from abdm.services.eka_client import EKAClient

def verify_init_linking_payload():
    """Verify that initiate_link_care_contexts constructs the correct payload"""
    print("\n🔹 Verifying Link Init Payload...")
    
    # 1. Setup Mock
    client = EKAClient()
    # Mock the _make_request method to inspect what it receives
    client._make_request = MagicMock(return_value={"txn_id": "test_txn"})
    
    # 2. Call the method
    txn_id = "TXN_123"
    patient_ref_id = "PAT_REF_456"
    cc_ref_id = "CC_REF_789"
    
    client.initiate_link_care_contexts(txn_id, patient_ref_id, cc_ref_id)
    
    # 3. Verify arguments
    client._make_request.assert_called_once()
    args, kwargs = client._make_request.call_args
    
    method = args[0]
    url = args[1]
    data = kwargs.get('data')
    
    print(f"   Method: {method}")
    print(f"   URL: {url}")
    print(f"   Data: {data}")
    
    assert method == 'POST'
    assert url == '/abdm/v1/care-contexts/discover/link/init'
    assert data['txn_id'] == txn_id
    assert data['patient_ref_id'] == patient_ref_id
    assert data['cc_ref_id'] == cc_ref_id
    
    # Check for extra invalid keys
    assert 'patient' not in data, "❌ Payload should NOT contain 'patient' object"
    assert 'care_contexts' not in data, "❌ Payload should NOT contain 'care_contexts' list"
    
    print("✅ SUCCESS: Payload matches API documentation requirements.")

if __name__ == "__main__":
    try:
        verify_init_linking_payload()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        exit(1)
