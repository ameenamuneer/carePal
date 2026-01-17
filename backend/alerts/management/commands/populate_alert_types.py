from django.core.management.base import BaseCommand
from alerts.models import AlertType

class Command(BaseCommand):
    help = 'Populates the database with default alert types'

    def handle(self, *args, **options):
        self.stdout.write('Populating alert types...')
        
        alert_types = [
            # Vital Anomalies
            {
                'code': 'VITAL_ANOMALY',
                'name': 'Vital Sign Anomaly',
                'category': 'VITAL_ANOMALY',
                'default_severity': 'WARNING',
                'message_template': 'Abnormal {vital_type} reading detected: {value} {unit}',
                'default_channels': ['in_app', 'push'],
                'requires_acknowledgment': True,
                'auto_escalate_minutes': 60,
                'allow_grouping': True,
                'grouping_window_minutes': 60
            },
            {
                'code': 'VITAL_CRITICAL',
                'name': 'Critical Vital Sign',
                'category': 'VITAL_ANOMALY',
                'default_severity': 'CRITICAL',
                'message_template': 'CRITICAL {vital_type} reading detected: {value} {unit}. Immediate attention required.',
                'default_channels': ['in_app', 'push', 'sms', 'email'],
                'requires_acknowledgment': True,
                'auto_escalate_minutes': 15,
                'allow_grouping': False
            },
            
            # Medication
            {
                'code': 'MEDICATION_MISSED',
                'name': 'Missed Medication',
                'category': 'MEDICATION',
                'default_severity': 'WARNING',
                'message_template': 'Missed dose of {medication} scheduled for {scheduled_time}',
                'default_channels': ['in_app', 'push'],
                'requires_acknowledgment': True,
                'auto_escalate_minutes': 120,
                'allow_grouping': True,
                'grouping_window_minutes': 240
            },
            {
                'code': 'MEDICATION_REMINDER',
                'name': 'Medication Reminder',
                'category': 'MEDICATION',
                'default_severity': 'INFO',
                'message_template': 'Time to take {medication}',
                'default_channels': ['in_app', 'push'],
                'requires_acknowledgment': False,
                'allow_grouping': True
            },
            
            # Device
            {
                'code': 'DEVICE_OFFLINE',
                'name': 'Device Offline',
                'category': 'DEVICE',
                'default_severity': 'WARNING',
                'message_template': 'Device {device_name} has been offline for {duration}',
                'default_channels': ['in_app', 'push'],
                'requires_acknowledgment': False,
                'allow_grouping': True,
                'grouping_window_minutes': 360
            },
            {
                'code': 'LOW_BATTERY',
                'name': 'Low Battery',
                'category': 'DEVICE',
                'default_severity': 'INFO',
                'message_template': 'Device {device_name} battery is low ({level}%)',
                'default_channels': ['in_app', 'push'],
                'requires_acknowledgment': False,
                'allow_grouping': True,
                'grouping_window_minutes': 1440
            },
            
            # Health Trends
            {
                'code': 'HEART_RATE_TREND',
                'name': 'Abnormal Heart Rate Trend',
                'category': 'HEALTH_TREND',
                'default_severity': 'WARNING',
                'message_template': 'Consistent abnormal heart rate detected over past {duration}',
                'default_channels': ['in_app', 'push', 'email'],
                'requires_acknowledgment': True,
                'auto_escalate_minutes': 240,
                'allow_grouping': True
            },
            {
                'code': 'SLEEP_QUALITY',
                'name': 'Poor Sleep Quality',
                'category': 'HEALTH_TREND',
                'default_severity': 'INFO',
                'message_template': 'Sleep quality has been poor for {days} consecutive days',
                'default_channels': ['in_app'],
                'requires_acknowledgment': False,
                'allow_grouping': True
            },
            
            # Emergency
            {
                'code': 'FALL_DETECTED',
                'name': 'Fall Detected',
                'category': 'EMERGENCY',
                'default_severity': 'EMERGENCY',
                'message_template': 'Fall detected for {patient_name} at {time}. Location: {location}',
                'default_channels': ['in_app', 'push', 'sms', 'email', 'voice_call'],
                'requires_acknowledgment': True,
                'auto_escalate_minutes': 5,
                'allow_grouping': False
            },
            {
                'code': 'SOS_TRIGGERED',
                'name': 'SOS Triggered',
                'category': 'EMERGENCY',
                'default_severity': 'EMERGENCY',
                'message_template': 'SOS trigger activated by {patient_name} at {time}',
                'default_channels': ['in_app', 'push', 'sms', 'email', 'voice_call'],
                'requires_acknowledgment': True,
                'auto_escalate_minutes': 5,
                'allow_grouping': False
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for data in alert_types:
            obj, created = AlertType.objects.update_or_create(
                code=data['code'],
                defaults=data
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
                
        self.stdout.write(self.style.SUCCESS(
            f'Successfully populated alert types. Created: {created_count}, Updated: {updated_count}'
        ))
