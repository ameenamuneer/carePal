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
    # Medications tasks (MINIMAL - AI DRIVEN)
    'prepare-next-day-medications': {
        'task': 'medications.tasks.prepare_next_day_medications',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
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
    # Alert Tasks
    'check-alert-escalation': {
        'task': 'alerts.tasks.check_alert_escalation',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'expire-old-alerts': {
        'task': 'alerts.tasks.expire_old_alerts',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    'compute-alert-statistics': {
        'task': 'alerts.tasks.compute_alert_statistics',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'retry-failed-deliveries': {
        'task': 'alerts.tasks.retry_failed_deliveries',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    # Family Tasks
    'send-care-schedule-reminders': {
        'task': 'family.tasks.send_care_schedule_reminders',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'check-overdue-schedules': {
        'task': 'family.tasks.check_overdue_schedules',
        'schedule': crontab(minute='0', hour='*'),  # Hourly
    },
    'expire-old-invitations': {
        'task': 'family.tasks.expire_old_invitations',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'send-daily-family-summary': {
        'task': 'family.tasks.send_daily_family_summary',
        'schedule': crontab(minute='0', hour='*'),  # Check hourly for configured times
    },
    'cleanup-old-activity-logs': {
        'task': 'family.tasks.cleanup_old_activity_logs',
        'schedule': crontab(day_of_week='sunday', hour=0, minute=0),  # Weekly
    },
    # Analytics Tasks
    'compute-daily-metrics': {
        'task': 'analytics.tasks.compute_daily_metrics',
        'schedule': crontab(hour=0, minute=5),  # Daily at 00:05
    },
    'compute-weekly-metrics': {
        'task': 'analytics.tasks.compute_weekly_metrics',
        'schedule': crontab(day_of_week=0, hour=0, minute=30),  # Sundays at 00:30
    },
    'compute-monthly-metrics': {
        'task': 'analytics.tasks.compute_monthly_metrics',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),  # 1st of month at 01:00
    },
    'compute-trend-analysis': {
        'task': 'analytics.tasks.compute_trend_analysis',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),  # Sundays at 02:00
    },
    'compute-risk-scores': {
        'task': 'analytics.tasks.compute_risk_scores',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    'process-scheduled-reports': {
        'task': 'analytics.tasks.process_scheduled_reports',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-old-dashboard-snapshots': {
        'task': 'analytics.tasks.cleanup_old_dashboard_snapshots',
        'schedule': crontab(minute=30),  # Every hour at :30
    },
}
