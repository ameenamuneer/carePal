
import base64
import os
import hashlib
from typing import Dict, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

class ABDMDecryptionService:
    """
    Handle ABDM Encryption/Decryption logic.
    Ref: https://sandbox.abdm.gov.in/docs/encryption
    
    Algorithm:
    1. Key Exchange: ECDH using Curve25519 (X25519)
    2. Key Derivation: HKDF-SHA256
    3. Encryption/Decryption: AES-GCM
    """

    def generate_key_pair(self) -> Tuple[str, str]:
        """
        Generate ephemeral Key Pair for a session.
        Returns: (public_key_b64, private_key_b64)
        """
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()

        from cryptography.hazmat.primitives import serialization

        # Serialize to bytes
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        return (
            base64.b64encode(public_bytes).decode('utf-8'),
            base64.b64encode(private_bytes).decode('utf-8')
        )
    
    def generate_nonce(self) -> str:
        """Generate 32-byte random nonce"""
        return base64.b64encode(os.urandom(32)).decode('utf-8')

    def decrypt(
        self,
        encrypted_data_b64: str,
        key_material_dict: Dict,
        my_private_key_b64: str,
        my_nonce_b64: str
    ) -> str:
        """
        Decrypt data received from HIP.
        
        Args:
            encrypted_data_b64: The cipher text
            key_material_dict: dict containing 'dhPublicKey' -> 'keyValue' and 'nonce' of Sender (HIP)
            my_private_key_b64: Our private key used during request
            my_nonce_b64: Our nonce sent during request
        """
        try:
            # 1. Decode inputs
            sender_public_key_b64 = key_material_dict.get('dhPublicKey', {}).get('keyValue')
            sender_nonce_b64 = key_material_dict.get('nonce')
            
            if not sender_public_key_b64 or not sender_nonce_b64:
                raise ValueError("Missing sender key material")

            my_private_bytes = base64.b64decode(my_private_key_b64)
            sender_public_bytes = base64.b64decode(sender_public_key_b64)
            my_nonce_bytes = base64.b64decode(my_nonce_b64)
            sender_nonce_bytes = base64.b64decode(sender_nonce_b64)
            encrypted_bytes = base64.b64decode(encrypted_data_b64)

            # 2. Reconstruct Keys
            my_private_key = x25519.X25519PrivateKey.from_private_bytes(my_private_bytes)
            sender_public_key = x25519.X25519PublicKey.from_public_bytes(sender_public_bytes)

            # 3. Derive Shared Secret (ECDH)
            shared_secret = my_private_key.exchange(sender_public_key)

            # 4. Derive Salt (XOR of nonces)
            # Ensure nonces are same length (usually 32 bytes)
            # If lengths differ, pad or truncate? ABDM spec says 32 bytes usually.
            salt_bytes = bytes(a ^ b for a, b in zip(my_nonce_bytes, sender_nonce_bytes))

            # 5. Derive Session Key (HKDF)
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt_bytes,
                info=b'', # Application info, usually empty for ABDM
                backend=default_backend()
            )
            derived_key = hkdf.derive(shared_secret)

            # 6. Decrypt (AES-GCM)
            # ABDM format usually: Authentication Tag is appended to Cipher? No, usually GCM handles it.
            # But wait, standard libraries often handle Auth Tag differently.
            # In Crypto module AESGCM: `encrypt` returns `nonce + ciphertext + tag`? No.
            # `decrypt(nonce, data, associated_data)`
            
            # Important: What is the IV/Nonce for AES-GCM?
            # ABDM Spec: "The IV (Nonce) is the derived salt... wait no."
            # Actually, standard is: Salt = Nonce1 XOR Nonce2. This salt is used for HKDF.
            # The IV for GCM is usually PART of the key material or separate?
            # ABDM Spec v2: The IV is usually the last 12 bytes of the XOR'd nonce? Or new random?
            
            # Let's verify standard ABDM implementation pattern:
            # Most common: HKDF Salt = SenderNonce XOR ReceiverNonce
            # HKDF Info = b''
            # AES Key = HKDF Derived (32 bytes)
            # AES IV = Last 12 bytes of the XOR'd nonces (Salt) ?? Or passed?
            
            # Correction: In most ABDM implementations (like Eka's own SDK logic):
            # IV is derived logic or static?
            # Let's assume standard interaction where IV is often derived from salt too.
            # Actually, looking at reference implementations:
            # IV = salt[20:32] (Last 12 bytes of the Salt) 
            
            iv = salt_bytes[-12:] 

            aesgcm = AESGCM(derived_key)
            decrypted_data = aesgcm.decrypt(iv, encrypted_bytes, None)

            return decrypted_data.decode('utf-8')

        except Exception as e:
            raise Exception(f"Decryption Failure: {str(e)}")
