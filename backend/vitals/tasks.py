from celery import shared_task
from django.utils import timezone
from django.db.models import Avg, Min, Max, Count, StdDev, Q
from datetime import timedelta
from .models import (
    VitalReading, VitalTrendAnalysis, ContinuousVitalSession,
    VitalType, DataSource
)
from patients.models import PatientProfile
import logging

logger = logging.getLogger(__name__)


@shared_task
def compute_vital_trends():
    """
    Compute trend analysis for all active patients
    Run this task periodically (e.g., every hour)
    """
    patients = PatientProfile.objects.filter(is_active=True)
    vital_types = VitalType.objects.filter(is_active=True)
    
    periods = [
        ('last_24h', timedelta(hours=24)),
        ('last_7days', timedelta(days=7)),
        ('last_30days', timedelta(days=30))
    ]
    
    for patient in patients:
        for vital_type in vital_types:
            for period_label, period_delta in periods:
                try:
                    _compute_trend_for_period(patient, vital_type, period_label, period_delta)
                except Exception as e:
                    logger.error(
                        f"Error computing trend for patient {patient.id}, "
                        f"vital {vital_type.id}, period {period_label}: {str(e)}"
                    )
    
    logger.info("Vital trends computation completed")


def _compute_trend_for_period(patient, vital_type, period_label, period_delta):
    """Helper function to compute trend for a specific period"""
    end_time = timezone.now()
    start_time = end_time - period_delta
    
    # Get readings for this period
    readings = VitalReading.objects.filter(
        patient=patient,
        vital_type=vital_type,
        measured_at__gte=start_time,
        measured_at__lte=end_time,
        is_deleted=False
    )
    
    reading_count = readings.count()
    
    if reading_count == 0:
        return
    
    # Calculate statistics
    stats = readings.aggregate(
        avg=Avg('value'),
        min=Min('value'),
        max=Max('value'),
        std=StdDev('value'),
        anomaly_count=Count('id', filter=Q(is_anomaly=True)),
        critical_count=Count('id', filter=Q(anomaly_severity='CRITICAL'))
    )
    
    # Determine trend direction
    # Compare with previous period
    previous_start = start_time - period_delta
    previous_readings = VitalReading.objects.filter(
        patient=patient,
        vital_type=vital_type,
        measured_at__gte=previous_start,
        measured_at__lt=start_time,
        is_deleted=False
    )
    
    previous_avg = previous_readings.aggregate(avg=Avg('value'))['avg']
    
    if previous_avg and stats['avg']:
        trend_percentage = ((stats['avg'] - previous_avg) / previous_avg) * 100
        
        if abs(trend_percentage) < 5:
            trend_direction = 'STABLE'
        elif trend_percentage > 5:
            # Determine if improving or declining based on vital type
            # For most vitals, increase is declining (BP, glucose, etc.)
            # This is simplified - real logic would be vital-specific
            trend_direction = 'DECLINING'
        else:
            trend_direction = 'IMPROVING'
    else:
        trend_percentage = 0
        trend_direction = 'STABLE'
    
    # Generate insights
    insights = _generate_insights(
        vital_type, stats, trend_direction, trend_percentage, reading_count
    )
    
    # Create or update trend analysis
    VitalTrendAnalysis.objects.update_or_create(
        patient=patient,
        vital_type=vital_type,
        period_label=period_label,
        period_start=start_time,
        defaults={
            'period_end': end_time,
            'reading_count': reading_count,
            'average_value': stats['avg'] or 0,
            'min_value': stats['min'] or 0,
            'max_value': stats['max'] or 0,
            'std_deviation': stats['std'],
            'trend_direction': trend_direction,
            'trend_percentage': trend_percentage,
            'anomaly_count': stats['anomaly_count'],
            'critical_anomaly_count': stats['critical_count'],
            'insights': insights
        }
    )


def _generate_insights(vital_type, stats, trend_direction, trend_percentage, reading_count):
    """Generate AI-style insights about the trend"""
    insights = []
    
    # Reading frequency insight
    if reading_count < 3:
        insights.append(f"Low reading frequency ({reading_count} readings). More frequent monitoring recommended.")
    
    # Trend insight
    if trend_direction == 'IMPROVING':
        insights.append(f"{vital_type.name} showing improvement ({abs(trend_percentage):.1f}% decrease)")
    elif trend_direction == 'DECLINING':
        insights.append(f"{vital_type.name} trending upward ({abs(trend_percentage):.1f}% increase). Monitor closely.")
    elif trend_direction == 'STABLE':
        insights.append(f"{vital_type.name} stable with minimal variation")
    
    # Anomaly insight
    if stats['anomaly_count'] > 0:
        insights.append(f"{stats['anomaly_count']} anomalous readings detected")
        if stats['critical_count'] > 0:
            insights.append(f"⚠️ {stats['critical_count']} critical readings require immediate attention")
    
    # Variability insight
    if stats['std'] and stats['avg']:
        cv = (stats['std'] / stats['avg']) * 100  # Coefficient of variation
        if cv > 20:
            insights.append(f"High variability detected (CV: {cv:.1f}%). Consider lifestyle factors.")
    
    return insights


@shared_task
def sync_cloud_data_sources():
    """
    Sync data from cloud-based sources (Fitbit, Apple Health)
    Run this task periodically (e.g., every 15 minutes)
    """
    cloud_sources = DataSource.objects.filter(
        source_type='CLOUD_API',
        is_active=True
    )
    
    for source in cloud_sources:
        try:
            _sync_cloud_source(source)
        except Exception as e:
            logger.error(f"Error syncing cloud source {source.id}: {str(e)}")
    
    logger.info(f"Cloud data sync completed for {cloud_sources.count()} sources")


def _sync_cloud_source(source):
    """
    Sync data from a specific cloud source
    This is a placeholder - actual implementation would use APIs
    """
    # Check if it's time to sync
    if source.last_sync_at:
        time_since_sync = timezone.now() - source.last_sync_at
        if time_since_sync.total_seconds() < (source.sync_frequency_minutes * 60):
            return  # Too soon to sync
    
    # Here you would implement actual API calls to:
    # - Fitbit API: https://dev.fitbit.com/build/reference/web-api/
    # - Apple HealthKit Cloud: https://developer.apple.com/health-fitness/
    
    # For now, just update last_sync_at
    source.last_sync_at = timezone.now()
    source.save()
    
    logger.info(f"Synced cloud source: {source.device_name}")


@shared_task
def update_continuous_session_stats(session_id):
    """
    Update statistics for a continuous monitoring session
    Called when session receives new readings
    """
    try:
        session = ContinuousVitalSession.objects.get(session_id=session_id)
        
        readings = VitalReading.objects.filter(
            session_id=session_id,
            is_deleted=False
        )
        
        stats = readings.aggregate(
            total=Count('id'),
            avg=Avg('value'),
            min=Min('value'),
            max=Max('value')
        )
        
        session.total_readings = stats['total'] or 0
        session.average_value = stats['avg']
        session.min_value = stats['min']
        session.max_value = stats['max']
        session.save()
        
        logger.info(f"Updated session {session_id} stats: {stats['total']} readings")
        
    except ContinuousVitalSession.DoesNotExist:
        logger.error(f"Session {session_id} not found")


@shared_task
def cleanup_old_continuous_readings():
    """
    Archive or cleanup very old continuous readings to manage database size
    Keep only aggregated data for old sessions
    Run this task daily
    """
    # Keep detailed readings for last 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    
    old_readings = VitalReading.objects.filter(
        measured_at__lt=cutoff_date,
        session_id__isnull=False  # Only continuous readings
    )
    
    count = old_readings.count()
    
    # In production, you might archive to data warehouse instead of deleting
    # For now, just mark as deleted
    old_readings.update(is_deleted=True, deleted_at=timezone.now())
    
    logger.info(f"Cleaned up {count} old continuous readings")


@shared_task
def check_vital_alerts(patient_id, reading_id):
    """
    Check if a vital reading should trigger an alert
    Called immediately after a reading is created
    """
    try:
        reading = VitalReading.objects.get(id=reading_id)
        
        if reading.is_anomaly and reading.anomaly_severity in ['HIGH', 'CRITICAL']:
            # Import here to avoid circular import
            from alerts.tasks import create_vital_alert
            
            create_vital_alert.delay(reading_id)
            logger.info(f"Alert triggered for reading {reading_id}")
        
    except VitalReading.DoesNotExist:
        logger.error(f"Reading {reading_id} not found")
