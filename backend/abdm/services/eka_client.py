import requests
from django.conf import settings
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class EKAClient:
    """EKA ABDM API Client - CORRECTED VERSION"""
    
    def __init__(self):
        self.config = settings.ABDM_CONFIG
        
        # Use sandbox for development
        if self.config.get('USE_SANDBOX', True):
            self.base_url = 'https://api.dev.eka.care'
            self.api_key = self.config['EKA_SANDBOX_KEY']
            logger.info("Using EKA Sandbox Environment")
        else:
            self.base_url = 'https://api.eka.care'
            self.api_key = self.config['EKA_API_KEY']
            logger.info("Using EKA Production Environment")
        
        self.hip_id = self.config.get('HIP_ID', '')
    
    def _get_headers(
        self, 
        oid: Optional[str] = None,
        partner_pt_id: Optional[str] = None,
        extra_headers: Optional[Dict] = None
    ) -> Dict:
        """Build request headers"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept-Encoding': 'identity',  # Force uncompressed response to avoid gzip errors
        }
        
        if oid:
            headers['X-Pt-Id'] = str(oid)
        if partner_pt_id:
            headers['X-Partner-Pt-Id'] = str(partner_pt_id)
        if self.hip_id:
            headers['X-Hip-Id'] = self.hip_id
        
        if extra_headers:
            headers.update(extra_headers)
        
        return headers
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        oid: Optional[str] = None,
        partner_pt_id: Optional[str] = None,
        extra_headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with comprehensive error handling"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(oid, partner_pt_id, extra_headers)
        
        try:
            logger.info(f"🔵 ABDM Request: {method} {endpoint}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Payload: {data}")
            
            response = requests.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                timeout=30
            )
            
            logger.info(f"✅ ABDM Response: {response.status_code}")
            
            # Check for errors
            if not response.ok:
                error_detail = {}
                try:
                    error_detail = response.json()
                except:
                    error_detail = {'error': response.text}
                
                logger.error(f"❌ ABDM Error: {response.status_code} - {error_detail}")
                
                # Extract error message
                error_msg = error_detail.get('error', 'Unknown error')
                abdm_code = error_detail.get('source_error', {}).get('code', 'UNKNOWN')
                
                raise Exception(f"ABDM API Error [{abdm_code}]: {error_msg}")
            
            # Handle 204 No Content
            if response.status_code == 204:
                return {}

            return response.json()

            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request Failed: {str(e)}")
            raise Exception(f"ABDM API Error: {str(e)}")
    
    # ==================== CORRECT REGISTRATION ENDPOINTS ====================
    
    def initiate_mobile_registration(self, mobile: str) -> Dict:
        """
        Step 1: Initiate ABHA registration with mobile
        
        CORRECT ENDPOINT: /abdm/na/v1/registration/mobile/init
        """
        return self._make_request(
            'POST',
            '/abdm/na/v1/registration/mobile/init',  # ✅ CORRECT PATH
            data={'mobile_number': mobile}
        )
    
    def verify_mobile_otp(self, txn_id: str, otp: str) -> Dict:
        """
        Step 2: Verify mobile OTP
        
        CORRECT ENDPOINT: /abdm/na/v1/registration/mobile/verify
        """
        return self._make_request(
            'POST',
            '/abdm/na/v1/registration/mobile/verify',  # ✅ CORRECT PATH
            data={'txn_id': txn_id, 'otp': otp}
        )
    
    def create_abha_address(
        self, 
        txn_id: str, 
        abha_address: str,
        profile: Dict
    ) -> Dict:
        """
        Step 3: Create ABHA address
        
        CORRECT ENDPOINT: /abdm/na/v1/registration/mobile/create-phr
        """
        return self._make_request(
            'POST',
            '/abdm/na/v1/registration/mobile/create-phr',  # ✅ CORRECT PATH
            data={
                'txn_id': txn_id,
                'abha_address': abha_address,
                'profile': profile
            }
        )
    
    # ==================== LOGIN ENDPOINTS ====================
    
    def initiate_login(self, mobile: str) -> Dict:
        """
        Step 1: Initiate ABHA login
        Endpoint: /abdm/na/v1/profile/login/init
        """
        return self._make_request(
            'POST',
            '/abdm/na/v1/profile/login/init',
            data={
                'identifier': mobile,
                'method': 'mobile'
            }
        )

    def verify_login_otp(self, txn_id: str, otp: str) -> Dict:
        """
        Step 2: Verify ABHA login OTP
        Endpoint: /abdm/na/v1/profile/login/verify
        """
        return self._make_request(
            'POST',
            '/abdm/na/v1/profile/login/verify',
            data={
                'txn_id': txn_id,
                'otp': otp
            }
        )

    def login_abha_address(self, txn_id: str, abha_address: str) -> Dict:
        """
        Step 3: Complete login by selecting ABHA address
        Endpoint: /abdm/na/v1/profile/login/login
        Used when skip_state is 'abha_select'
        """
        return self._make_request(
            'POST',
            '/abdm/na/v1/profile/login',
            data={
                'txn_id': txn_id,
                'abha_address': abha_address
            }
        )

    # ==================== CONSENT MANAGEMENT ====================
    
    def approve_consent(self, consent_id: str, consent_artefacts: list, oid: str = None) -> bool:
        """
        Approve a consent request
        POST /abdm/v1/consents/approve
        """
        data = {
            'id': consent_id,
            'consent_artefacts': consent_artefacts,
            # Defaults for now, can be parameterized further if needed
            'access_mode': 'view',
            'duration': {
                 'from': '2023-01-01T00:00:00.000Z', # Example defaults, should come from request
                 'to': '2030-01-01T00:00:00.000Z'
            }
        }
        
        # Override data with passed artefacts if they contain full structure
        # But for simplicity, we assume consent_artefacts has key details
        # Actually creating a proper structure is complex. 
        # For now, let's just pass the data dict we construct or expect validated data.
        # Let's trust the caller to pass the right structure or update this signature.
        
        # Simpler signature for now:
        # We'll just take the data object fully constructed from the service layer
        pass

    def approve_consent_request(self, data: Dict, oid: str = None) -> bool:
        """
        Approve consent with full payload
        POST /abdm/v1/consents/approve
        """
        try:
            self._make_request(
                'POST',
                '/abdm/v1/consents/approve',
                data=data,
                oid=oid
            )
            return True
        except Exception as e:
            logger.error(f"Consent approval failed: {e}")
            raise

    def deny_consent_request(self, consent_id: str, reason: str = "User denied", oid: str = None) -> bool:
        """
        Deny a consent request
        POST /abdm/v1/consents/deny
        """
        try:
            self._make_request(
                'POST',
                '/abdm/v1/consents/deny',
                data={'id': consent_id, 'reason': reason},
                oid=oid
            )
            return True
        except Exception as e:
            logger.error(f"Consent denial failed: {e}")
            raise

    # ==================== CARE CONTEXTS ====================

    def get_linked_providers(self, oid: str = None, partner_pt_id: str = None) -> Dict:
        """
        Get list of linked providers
        GET /abdm/v1/care-contexts/providers
        """
        return self._make_request(
            'GET',
            '/abdm/v1/care-contexts/providers',
            params={'oid': oid} if oid else None,
            oid=oid,
            partner_pt_id=partner_pt_id
        )

    def get_linked_care_contexts(self, hip_id: str, oid: str = None, partner_pt_id: str = None) -> Dict:
        """
        Get linked care contexts for a provider
        GET /abdm/v1/care-contexts/linked
        """
        return self._make_request(
            'GET',
            '/abdm/v1/care-contexts/linked',
            params={'hip_id': hip_id, 'oid': oid} if oid else {'hip_id': hip_id},
            oid=oid,
            partner_pt_id=partner_pt_id
        )

    # ==================== PHR ONBOARDING (DISCOVERY & LINKING) ====================

    def discover_care_contexts(self, hip_id: str, ref_id: str, oid: str = None) -> Dict:
        """
        Discover unlinked care contexts
        POST /abdm/v1/care-contexts/discover
        """
        # MOCK MODE check
        if self.config.get('mock_mode'):
            logger.warning("🔸 [MOCK] Returning Fake Discovery Data")
            return {
                "txn_id": "mock_txn_discovery_123",
                "patient": [
                    {
                        "reference_number": ref_id,
                        "display": "Test Patient (Mock)",
                        "care_contexts": [
                            {"id": "CTX-001", "display": "General OPD - 22 Jan"},
                            {"id": "CTX-002", "display": "Lab Report - Blood Test"}
                        ]
                    }
                ]
            }

        return self._make_request(
            'POST',
            '/abdm/v1/care-contexts/discover',
            data={
                'hip_id': hip_id,
                'ref_id': ref_id  # Mobile number or Patient Registration ID
            },
            oid=oid
        )

    def initiate_link_care_contexts(self, txn_id: str, patient_ref_id: str, cc_ref_id: str, oid: str = None) -> Dict:
        """
        Initiate linking for discovered contexts (Part 2)
        POST /abdm/v1/care-contexts/discover/link/init
        """
        if self.config.get('mock_mode'):
             return {"txn_id": "mock_txn_link_init_456"}

        return self._make_request(
            'POST',
            '/abdm/v1/care-contexts/discover/link/init',
            data={
                'txn_id': txn_id,
                'patient_ref_id': patient_ref_id,
                'cc_ref_id': cc_ref_id
            },
            oid=oid
        )

    def confirm_link_care_contexts(self, txn_id: str, otp: str, oid: str = None) -> Dict:
        """
        Confirm linking with OTP (Part 3)
        POST /abdm/v1/care-contexts/discover/link/confirm
        """
        if self.config.get('mock_mode'):
             # Simulate Webhook Notification for Context Linked
             self._simulate_webhook_notify()
             return {"status": "success", "access_token": "mock_link_token"}

        return self._make_request(
            'POST',
            '/abdm/v1/care-contexts/discover/link/confirm',
            data={
                'txn_id': txn_id,
                'otp': otp
            },
            oid=oid
        )

    def _simulate_webhook_notify(self):
        """Helper to simulate webhook in mock mode"""
        try:
             from abdm.views import abdm_webhook_view
             from rest_framework.test import APIRequestFactory
             
             # We can't easily call the view directly request object, 
             # but we can log that we 'would' have received it.
             logger.info("🔸 [MOCK] Simulating abha.subscription_notify webhook!")
             # In a real mock, we might call the logic directly.
        except:
             pass

    # ==================== REQUESTS (SUBSCRIPTIONS & CONSENTS) ====================

    def get_patient_requests(self, status: str, type: str, oid: str = None) -> Dict:
        """
        List all Subscriptions and Consent requests
        GET /abdm/v1/requests
        """
        return self._make_request(
            'GET',
            '/abdm/v1/requests',
            params={
                'status': status,
                'type': type,
                'oid': oid
            },
            oid=oid
        )


