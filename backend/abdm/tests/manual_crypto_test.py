
import os
import sys
import django
from django.conf import settings
import base64
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

# Setup minimal env for standalone run
if not settings.configured:
    settings.configure(DEBUG=True)

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from abdm.services.decryption import ABDMDecryptionService

def test_crypto_flow():
    print("🚀 Starting Crypto Test...")
    service = ABDMDecryptionService()

    # 1. Receiver (Us) Generates Keys
    my_public_b64, my_private_b64 = service.generate_key_pair()
    my_nonce_b64 = service.generate_nonce()
    print(f"✅ Generated Receiver Keys")

    # 2. Sender (HIP) Generates Keys
    sender_private_key = x25519.X25519PrivateKey.generate()
    sender_public_key = sender_private_key.public_key()
    
    sender_public_bytes = sender_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    sender_public_b64 = base64.b64encode(sender_public_bytes).decode('utf-8')
    sender_nonce = os.urandom(32)
    sender_nonce_b64 = base64.b64encode(sender_nonce).decode('utf-8')
    print(f"✅ Generated Sender Keys")

    # 3. Helper: Encrypt Data (Simulating HIP)
    # Derive Shared Secret
    my_public_bytes = base64.b64decode(my_public_b64)
    my_public_key_obj = x25519.X25519PublicKey.from_public_bytes(my_public_bytes)
    shared_secret_sender = sender_private_key.exchange(my_public_key_obj)

    # Derive Salt (XOR)
    my_nonce_bytes = base64.b64decode(my_nonce_b64)
    salt_bytes = bytes(a ^ b for a, b in zip(my_nonce_bytes, sender_nonce))

    # Derive Key
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt_bytes,
        info=b'',
        backend=default_backend()
    )
    derived_key = hkdf.derive(shared_secret_sender)

    # Encrypt
    aesgcm = AESGCM(derived_key)
    iv = salt_bytes[-12:]
    plaintext = b'{"resourceType": "Bundle", "type": "collection"}'
    ciphertext = aesgcm.encrypt(iv, plaintext, None)
    encrypted_b64 = base64.b64encode(ciphertext).decode('utf-8')
    print(f"✅ Encrypted Data: {encrypted_b64[:20]}...")

    # 4. Decrypt (Us)
    key_material = {
        'dhPublicKey': {'keyValue': sender_public_b64},
        'nonce': sender_nonce_b64
    }

    try:
        decrypted_text = service.decrypt(
            encrypted_b64,
            key_material,
            my_private_b64,
            my_nonce_b64
        )
        print(f"✅ Decrypted Data: {decrypted_text}")
        assert decrypted_text == plaintext.decode('utf-8')
        print("🎉 SUCCESS: End-to-End Crypto Flow Verified!")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        raise

if __name__ == "__main__":
    test_crypto_flow()
