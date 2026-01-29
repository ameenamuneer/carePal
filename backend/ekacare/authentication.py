import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class EkaCareAPIException(Exception):
    pass

class EkaCareAuth:
    BASE_URL = "https://api.eka.care"  # Validating this URL would be good, but assuming standard for now or PROD.
    # Note: User provided Client ID and Key. In a real app, these should be in settings.
    # I will stick them here for now as requested, or better, access from settings if I put them there.
    # For this implementation, I'll define them here to ensure they work immediately as per the prompt context.
    
    CLIENT_ID = "EC_1769663902995"
    SECRET_KEY = "eka_5409bc1e64d148cf91cf3234"

    @classmethod
    def get_headers(cls):
        return {
            'client-id': cls.CLIENT_ID,
            'client-key': cls.SECRET_KEY,
            'Content-Type': 'application/json'
        }

    @classmethod
    def make_request(cls, method, endpoint, data=None, params=None):
        url = f"{cls.BASE_URL}{endpoint}"
        headers = cls.get_headers()
        
        try:
            response = requests.request(
                method, 
                url, 
                headers=headers, 
                json=data, 
                params=params,
                timeout=30
            )
            
            # Raise for 4xx/5xx
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Eka.Care API Error: {str(e)}"
            if e.response.content:
                try:
                    error_json = e.response.json()
                    error_msg = f"{error_msg} - {error_json}"
                except:
                    error_msg = f"{error_msg} - {e.response.text}"
            
            logger.error(error_msg)
            raise EkaCareAPIException(error_msg)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Eka.Care Connection Error: {str(e)}")
            raise EkaCareAPIException(f"Connection failed: {str(e)}")
