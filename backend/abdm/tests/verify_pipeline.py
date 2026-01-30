
import os
import sys
import json
import base64
import django
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carepal.settings")
django.setup()

from abdm.callbacks.webhook_handler import WebhookHandler
from abdm.services.decryption import ABDMDecryptionService
from vitals.models import VitalReading

def verify_pipeline():
    print("🚀 Starting End-to-End Pipeline Verification...")

    # 1. Setup Keys (Simulating User Session)
    # 2. Setup Test Data (Sender/HIP side)
    service = ABDMDecryptionService()
    
    # Receiver (Us) Keys
    my_public_b64, my_private_b64 = service.generate_key_pair()
    my_nonce_b64 = service.generate_nonce()
    
    # Sender (HIP) Keys
    sender_private = x25519.X25519PrivateKey.generate()
    sender_public = sender_private.public_key()
    sender_public_bytes = sender_public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    sender_public_b64 = base64.b64encode(sender_public_bytes).decode('utf-8')
    sender_nonce = os.urandom(32)
    sender_nonce_b64 = base64.b64encode(sender_nonce).decode('utf-8')

    # 3. Encrypt Mock FHIR Bundle
    # BP: 120/80
    fhir_bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {
                        "coding": [{"system": "http://loinc.org", "code": "85354-9"}] 
                    },
                    "component": [
                        {
                            "code": {"coding": [{"code": "8480-6"}]}, # Systolic
                            "valueQuantity": {"value": 120, "unit": "mmHg"}
                        },
                        {
                            "code": {"coding": [{"code": "8462-4"}]}, # Diastolic
                            "valueQuantity": {"value": 80, "unit": "mmHg"}
                        }
                    ],
                    "effectiveDateTime": "2023-10-27T10:00:00Z"
                }
            }
        ]
    }
    
    # Encrypt Logic (Manual Re-implementation of what HIP would do)
    my_public_bytes = base64.b64decode(my_public_b64)
    my_public_key_obj = x25519.X25519PublicKey.from_public_bytes(my_public_bytes)
    shared_secret = sender_private.exchange(my_public_key_obj)
    
    my_nonce_bytes = base64.b64decode(my_nonce_b64)
    salt = bytes(a ^ b for a, b in zip(my_nonce_bytes, sender_nonce))
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b'',
        backend=default_backend()
    )
    key = hkdf.derive(shared_secret)
    iv = salt[-12:]
    
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, json.dumps(fhir_bundle).encode('utf-8'), None)
    encrypted_content = base64.b64encode(ciphertext).decode('utf-8')
    
    # 4. Construct Payload
    payload = {
        "transaction_id": "test_txn_123",
        "entries": [
            {"content": encrypted_content, "media": "application/fhir+json"}
        ],
        "key_material": {
            "dhPublicKey": {"keyValue": sender_public_b64},
            "nonce": sender_nonce_b64
        },
        # Inject our keys so the handler can decrypt
        "_dev_private_key": my_private_b64,
        "_dev_nonce": my_nonce_b64
    }

    print("📦 Payload constructed. Calling Handler...")
    
    # 5. Call Handler
    WebhookHandler.handle_data_fetch(payload)
    
    # 6. Verify Database
    print("🔍 verifying Database...")
    readings = VitalReading.objects.filter(
        values__systolic=120, 
        values__diastolic=80
    )
    
    if readings.exists():
        print(f"✅ SUCCESS: Found {readings.count()} vital reading(s) in DB!")
        print(f"   Reading: {readings.first().vital_type.code} - {readings.first().values}")
    else:
        print("❌ FAILURE: No matching reading found in DB.")

if __name__ == "__main__":
    verify_pipeline()
