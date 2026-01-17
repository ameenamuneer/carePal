import requests
from datetime import datetime, timedelta
from django.utils import timezone
from .base_client import BaseCloudClient
import logging

logger = logging.getLogger(__name__)


class FitbitClient(BaseCloudClient):
    """
    Fitbit API client
    Documentation: https://dev.fitbit.com/build/reference/web-api/
    """
    
    def refresh_token(self):
        """
        Refresh Fitbit access token
        """
        refresh_token = self.credential.get_refresh_token()
        if not refresh_token:
            logger.error("No refresh token available")
            return False
        
        try:
            response = requests.post(
                self.provider.token_url,
                auth=(self.provider.client_id, self.provider.client_secret),
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Update credential
            self.credential.set_access_token(data['access_token'])
            self.credential.set_refresh_token(data['refresh_token'])
            self.credential.expires_at = timezone.now() + timedelta(seconds=data['expires_in'])
            self.credential.status = 'ACTIVE'
            self.credential.save()
            
            # Update local token
            self.access_token = data['access_token']
            
            logger.info(f"Fitbit token refreshed for credential {self.credential.id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to refresh Fitbit token: {str(e)}")
            self.credential.status = 'ERROR'
            self.credential.last_error = str(e)
            self.credential.save()
            return False
    
    def get_user_profile(self):
        """Get user profile information"""
        return self.make_request('GET', 'user/-/profile.json')
    
    def get_heart_rate(self, start_date, end_date):
        """
        Get heart rate data
        Returns intraday time series
        """
        results = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            try:
                # Get intraday heart rate (1min detail level)
                data = self.make_request(
                    'GET',
                    f'user/-/activities/heart/date/{date_str}/1d/1min.json'
                )
                
                if 'activities-heart-intraday' in data:
                    dataset = data['activities-heart-intraday'].get('dataset', [])
                    
                    for point in dataset:
                        results.append({
                            'timestamp': f"{date_str} {point['time']}",
                            'value': point['value'],
                            'type': 'heart_rate'
                        })
            
            except Exception as e:
                logger.error(f"Error fetching Fitbit heart rate for {date_str}: {str(e)}")
            
            current_date += timedelta(days=1)
        
        return results
    
    def get_steps(self, start_date, end_date):
        """Get steps data"""
        results = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            try:
                # Get steps for the day
                data = self.make_request(
                    'GET',
                    f'user/-/activities/steps/date/{date_str}/1d.json'
                )
                
                if 'activities-steps' in data and data['activities-steps']:
                    steps = int(data['activities-steps'][0].get('value', 0))
                    
                    results.append({
                        'timestamp': f"{date_str} 23:59:59",  # End of day
                        'value': steps,
                        'type': 'steps'
                    })
            
            except Exception as e:
                logger.error(f"Error fetching Fitbit steps for {date_str}: {str(e)}")
            
            current_date += timedelta(days=1)
        
        return results
    
    def get_sleep(self, start_date, end_date):
        """Get sleep data"""
        results = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            try:
                data = self.make_request(
                    'GET',
                    f'user/-/sleep/date/{date_str}.json'
                )
                
                if 'sleep' in data:
                    for sleep_record in data['sleep']:
                        if sleep_record.get('isMainSleep'):
                            # Get total minutes asleep
                            minutes = sleep_record.get('minutesAsleep', 0)
                            hours = round(minutes / 60, 2)
                            
                            results.append({
                                'timestamp': sleep_record['startTime'],
                                'value': hours,
                                'type': 'sleep',
                                'duration_minutes': minutes
                            })
            
            except Exception as e:
                logger.error(f"Error fetching Fitbit sleep for {date_str}: {str(e)}")
            
            current_date += timedelta(days=1)
        
        return results
    
    def get_activities(self, start_date, end_date):
        """Get activity/exercise data"""
        results = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            try:
                data = self.make_request(
                    'GET',
                    f'user/-/activities/date/{date_str}.json'
                )
                
                if 'activities' in data:
                    for activity in data['activities']:
                        results.append({
                            'timestamp': activity['startTime'],
                            'activity_name': activity['activityName'],
                            'duration_minutes': activity.get('duration', 0) / 60000,  # Convert ms to min
                            'calories': activity.get('calories', 0),
                            'distance': activity.get('distance', 0)
                        })
            
            except Exception as e:
                logger.error(f"Error fetching Fitbit activities for {date_str}: {str(e)}")
            
            current_date += timedelta(days=1)
        
        return results
    
    def get_spo2(self, start_date, end_date):
        """Get SpO2 data (requires premium subscription)"""
        results = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            try:
                data = self.make_request(
                    'GET',
                    f'user/-/spo2/date/{date_str}.json'
                )
                
                if 'value' in data:
                    results.append({
                        'timestamp': date_str,
                        'value': data['value'].get('avg', 0),
                        'type': 'spo2'
                    })
            
            except Exception as e:
                logger.error(f"Error fetching Fitbit SpO2 for {date_str}: {str(e)}")
            
            current_date += timedelta(days=1)
        
        return results
