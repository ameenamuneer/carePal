from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from django.utils import timezone
from .base_client import BaseCloudClient
import logging

logger = logging.getLogger(__name__)


class GoogleFitClient(BaseCloudClient):
    """
    Google Fit API client
    Documentation: https://developers.google.com/fit/rest
    """
    
    def __init__(self, credential):
        super().__init__(credential)
        self.service = self._build_service()
    
    def _build_service(self):
        """Build Google Fit API service"""
        creds = Credentials(
            token=self.access_token,
            refresh_token=self.credential.get_refresh_token(),
            token_uri=self.provider.token_url,
            client_id=self.provider.client_id,
            client_secret=self.provider.client_secret
        )
        
        return build('fitness', 'v1', credentials=creds, cache_discovery=False)
    
    def refresh_token(self):
        """Refresh Google Fit access token"""
        try:
            # Google client library handles token refresh automatically
            # We just need to rebuild the service
            self.service = self._build_service()
            
            # Update credential in database
            new_token = self.service._http.credentials.token
            self.credential.set_access_token(new_token)
            self.credential.expires_at = timezone.now() + timedelta(hours=1)
            self.credential.status = 'ACTIVE'
            self.credential.save()
            
            self.access_token = new_token
            
            logger.info(f"Google Fit token refreshed for credential {self.credential.id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to refresh Google Fit token: {str(e)}")
            self.credential.status = 'ERROR'
            self.credential.last_error = str(e)
            self.credential.save()
            return False
    
    def _get_data_source(self, data_type):
        """Get data source ID for a data type"""
        data_sources = {
            'heart_rate': 'derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm',
            'steps': 'derived:com.google.step_count.delta:com.google.android.gms:estimated_steps',
            'calories': 'derived:com.google.calories.expended:com.google.android.gms:merge_calories_expended',
            'distance': 'derived:com.google.distance.delta:com.google.android.gms:merge_distance_delta',
            'weight': 'derived:com.google.weight:com.google.android.gms:merge_weight',
        }
        return data_sources.get(data_type)
    
    def _datetime_to_nanos(self, dt):
        """Convert datetime to nanoseconds (Google Fit format)"""
        return int(dt.timestamp() * 1000000000)
    
    def get_heart_rate(self, start_date, end_date):
        """Get heart rate data"""
        try:
            dataset_id = f"{self._datetime_to_nanos(datetime.combine(start_date, datetime.min.time()))}-{self._datetime_to_nanos(datetime.combine(end_date, datetime.max.time()))}"
            
            data_source = self._get_data_source('heart_rate')
            
            dataset = self.service.users().dataSources().datasets().get(
                userId='me',
                dataSourceId=data_source,
                datasetId=dataset_id
            ).execute()
            
            results = []
            for point in dataset.get('point', []):
                timestamp = datetime.fromtimestamp(int(point['startTimeNanos']) / 1000000000)
                value = point['value'][0].get('fpVal', 0)
                
                results.append({
                    'timestamp': timestamp.isoformat(),
                    'value': value,
                    'type': 'heart_rate'
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Error fetching Google Fit heart rate: {str(e)}")
            return []
    
    def get_steps(self, start_date, end_date):
        """Get steps data"""
        try:
            dataset_id = f"{self._datetime_to_nanos(datetime.combine(start_date, datetime.min.time()))}-{self._datetime_to_nanos(datetime.combine(end_date, datetime.max.time()))}"
            
            data_source = self._get_data_source('steps')
            
            dataset = self.service.users().dataSources().datasets().get(
                userId='me',
                dataSourceId=data_source,
                datasetId=dataset_id
            ).execute()
            
            # Aggregate steps by day
            daily_steps = {}
            for point in dataset.get('point', []):
                timestamp = datetime.fromtimestamp(int(point['startTimeNanos']) / 1000000000)
                date_str = timestamp.date().isoformat()
                steps = int(point['value'][0].get('intVal', 0))
                
                daily_steps[date_str] = daily_steps.get(date_str, 0) + steps
            
            results = []
            for date_str, steps in daily_steps.items():
                results.append({
                    'timestamp': f"{date_str} 23:59:59",
                    'value': steps,
                    'type': 'steps'
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Error fetching Google Fit steps: {str(e)}")
            return []
    
    def get_sleep(self, start_date, end_date):
        """Get sleep data"""
        try:
            # Google Fit sleep API
            start_time_millis = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
            end_time_millis = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)
            
            sleep_data = self.service.users().sessions().list(
                userId='me',
                startTime=datetime.fromtimestamp(start_time_millis/1000).isoformat() + 'Z',
                endTime=datetime.fromtimestamp(end_time_millis/1000).isoformat() + 'Z',
                activityType=72  # Sleep activity type
            ).execute()
            
            results = []
            for session in sleep_data.get('session', []):
                start_time = datetime.fromisoformat(session['startTimeMillis'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(session['endTimeMillis'].replace('Z', '+00:00'))
                
                duration_minutes = (end_time - start_time).total_seconds() / 60
                hours = round(duration_minutes / 60, 2)
                
                results.append({
                    'timestamp': start_time.isoformat(),
                    'value': hours,
                    'type': 'sleep',
                    'duration_minutes': int(duration_minutes)
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Error fetching Google Fit sleep: {str(e)}")
            return []
    
    def get_activities(self, start_date, end_date):
        """Get activity sessions"""
        try:
            start_time_millis = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
            end_time_millis = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)
            
            sessions = self.service.users().sessions().list(
                userId='me',
                startTime=datetime.fromtimestamp(start_time_millis/1000).isoformat() + 'Z',
                endTime=datetime.fromtimestamp(end_time_millis/1000).isoformat() + 'Z'
            ).execute()
            
            results = []
            for session in sessions.get('session', []):
                if session.get('activityType') != 72:  # Exclude sleep
                    start_time = datetime.fromisoformat(session['startTimeMillis'].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(session['endTimeMillis'].replace('Z', '+00:00'))
                    
                    duration_minutes = (end_time - start_time).total_seconds() / 60
                    
                    results.append({
                        'timestamp': start_time.isoformat(),
                        'activity_name': session.get('name', 'Activity'),
                        'duration_minutes': int(duration_minutes),
                        'activity_type': session.get('activityType')
                    })
            
            return results
        
        except Exception as e:
            logger.error(f"Error fetching Google Fit activities: {str(e)}")
            return []
