import requests
from abc import ABC, abstractmethod
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class BaseCloudClient(ABC):
    """
    Abstract base class for cloud API clients
    """
    
    def __init__(self, credential):
        """
        Initialize client with CloudAPICredential
        """
        self.credential = credential
        self.provider = credential.provider
        self.access_token = credential.get_access_token()
        self.base_url = self.provider.api_base_url
    
    def get_headers(self):
        """Get authorization headers"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def make_request(self, method, endpoint, **kwargs):
        """
        Make API request with error handling
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self.get_headers()
        
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=30,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Token expired, try refresh
                if self.refresh_token():
                    # Retry with new token
                    headers = self.get_headers()
                    response = requests.request(
                        method,
                        url,
                        headers=headers,
                        timeout=30,
                        **kwargs
                    )
                    response.raise_for_status()
                    return response.json()
            
            logger.error(f"API request failed: {str(e)}")
            raise
        
        except Exception as e:
            logger.error(f"Unexpected error in API request: {str(e)}")
            raise
    
    @abstractmethod
    def refresh_token(self):
        """Refresh access token - implemented by each client"""
        pass
    
    @abstractmethod
    def get_heart_rate(self, start_date, end_date):
        """Get heart rate data"""
        pass
    
    @abstractmethod
    def get_steps(self, start_date, end_date):
        """Get steps data"""
        pass
    
    @abstractmethod
    def get_sleep(self, start_date, end_date):
        """Get sleep data"""
        pass
    
    @abstractmethod
    def get_activities(self, start_date, end_date):
        """Get activities/workouts data"""
        pass
