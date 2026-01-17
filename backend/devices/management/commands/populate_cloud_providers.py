from django.core.management.base import BaseCommand
from devices.models import CloudProvider


class Command(BaseCommand):
    help = 'Populate cloud providers catalog'
    
    def handle(self, *args, **kwargs):
        providers = [
            {
                'name': 'FITBIT',
                'display_name': 'Fitbit',
                'authorization_url': 'https://www.fitbit.com/oauth2/authorize',
                'token_url': 'https://api.fitbit.com/oauth2/token',
                'api_base_url': 'https://api.fitbit.com/1',
                'scopes': [
                    'activity', 'heartrate', 'location', 'nutrition',
                    'profile', 'settings', 'sleep', 'social', 'weight'
                ],
                'supports_webhooks': True,
                'webhook_url': 'https://api.fitbit.com/1/user/-/apiSubscriptions',
                'rate_limit_per_hour': 150,
                'sync_interval_minutes': 15,
                'supported_vitals': ['heart_rate', 'steps', 'sleep', 'spo2', 'calories']
            },
            {
                'name': 'GOOGLE_FIT',
                'display_name': 'Google Fit',
                'authorization_url': 'https://accounts.google.com/o/oauth2/v2/auth',
                'token_url': 'https://oauth2.googleapis.com/token',
                'api_base_url': 'https://www.googleapis.com/fitness/v1',
                'scopes': [
                    'https://www.googleapis.com/auth/fitness.activity.read',
                    'https://www.googleapis.com/auth/fitness.body.read',
                    'https://www.googleapis.com/auth/fitness.heart_rate.read',
                    'https://www.googleapis.com/auth/fitness.sleep.read'
                ],
                'supports_webhooks': False,
                'rate_limit_per_hour': 100,
                'sync_interval_minutes': 15,
                'supported_vitals': ['heart_rate', 'steps', 'sleep', 'weight', 'calories']
            },
            {
                'name': 'APPLE_HEALTH',
                'display_name': 'Apple Health',
                'authorization_url': '',  # Apple uses different OAuth
                'token_url': '',
                'api_base_url': '',
                'scopes': [],
                'supports_webhooks': False,
                'rate_limit_per_hour': 100,
                'sync_interval_minutes': 15,
                'supported_vitals': ['heart_rate', 'steps', 'sleep', 'blood_pressure']
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for provider_data in providers:
            provider, created = CloudProvider.objects.update_or_create(
                name=provider_data['name'],
                defaults=provider_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created: {provider.display_name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated: {provider.display_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted: {created_count} created, {updated_count} updated'
            )
        )
