from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')

app = Celery('carepal')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks schedule
app.conf.beat_schedule = {
    # Vitals tasks
    'compute-vital-trends-hourly': {
        'task': 'vitals.tasks.compute_vital_trends',
        'schedule': crontab(minute=0),  # Every hour
    },
    'sync-cloud-data-sources': {
        'task': 'vitals.tasks.sync_cloud_data_sources',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'cleanup-old-continuous-readings': {
        'task': 'vitals.tasks.cleanup_old_continuous_readings',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    # Medications tasks
    'send-medication-reminders': {
        'task': 'medications.tasks.send_medication_reminders',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'check-missed-medications': {
        'task': 'medications.tasks.check_missed_medications',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'compute-adherence-patterns': {
        'task': 'medications.tasks.compute_adherence_patterns',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'check-refill-needs': {
        'task': 'medications.tasks.check_refill_needs',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    # Devices tasks
    'sync-all-cloud-devices': {
        'task': 'devices.tasks.sync_all_cloud_devices',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'refresh-expired-tokens': {
        'task': 'devices.tasks.refresh_expired_tokens',
        'schedule': crontab(minute=0),  # Every hour
    },
    'detect-data-conflicts': {
        'task': 'devices.tasks.detect_data_conflicts',
        'schedule': crontab(minute=30),  # Every hour at :30
    },
    'cleanup-old-sync-logs': {
        'task': 'devices.tasks.cleanup_old_sync_logs',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
    },
    'check-device-health': {
        'task': 'devices.tasks.check_device_health',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}
