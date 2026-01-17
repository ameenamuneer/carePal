from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    CloudProvider, CloudAPICredential, DeviceSyncLog,
    DataConflict
)
from vitals.models import DataSource, VitalReading, VitalType
from .cloud_clients.fitbit_client import FitbitClient
from .cloud_clients.google_fit_client import GoogleFitClient
import logging

logger = logging.getLogger(__name__)


@shared_task
def sync_all_cloud_devices():
    """
    Sync all active cloud devices
    Run this task every 15 minutes
    """
    # Get all active cloud API credentials
    credentials = CloudAPICredential.objects.filter(
        status='ACTIVE',
        data_source__is_active=True
    )
    
    sync_count = 0
    
    for credential in credentials:
        # Check if it's time to sync based on provider's sync interval
        if credential.last_sync_at:
            time_since_sync = timezone.now() - credential.last_sync_at
            sync_interval = credential.provider.sync_interval_minutes
            
            if time_since_sync.total_seconds() < (sync_interval * 60):
                continue  # Too soon to sync
        
        # Trigger sync
        try:
            sync_device_data.delay(credential.data_source.id)
            sync_count += 1
        except Exception as e:
            logger.error(f"Error triggering sync for credential {credential.id}: {str(e)}")
    
    logger.info(f"Triggered {sync_count} cloud device syncs")
    return sync_count


@shared_task
def sync_device_data(data_source_id):
    """
    Sync data from a specific device
    """
    try:
        data_source = DataSource.objects.get(id=data_source_id)
        
        if data_source.source_type != 'CLOUD_API':
            logger.warning(f"Data source {data_source_id} is not a cloud API device")
            return
        
        # Get credential
        try:
            credential = CloudAPICredential.objects.get(data_source=data_source)
        except CloudAPICredential.DoesNotExist:
            logger.error(f"No credential found for data source {data_source_id}")
            return
        
        # Create sync log
        sync_log = DeviceSyncLog.objects.create(
            data_source=data_source,
            cloud_credential=credential,
            sync_type='SCHEDULED',
            status='STARTED'
        )
        
        try:
            # Get appropriate client
            if credential.provider.name == 'FITBIT':
                client = FitbitClient(credential)
            elif credential.provider.name == 'GOOGLE_FIT':
                client = GoogleFitClient(credential)
            else:
                raise ValueError(f"Unsupported provider: {credential.provider.name}")
            
            # Determine sync date range
            # Sync last 7 days on first sync, last 1 day on subsequent syncs
            end_date = timezone.now().date()
            
            if credential.last_sync_at:
                # Sync from last sync date
                start_date = credential.last_sync_at.date()
            else:
                # First sync - get last 7 days
                start_date = end_date - timedelta(days=7)
            
            sync_log.sync_from_date = timezone.make_aware(
                datetime.combine(start_date, datetime.min.time())
            )
            sync_log.sync_to_date = timezone.make_aware(
                datetime.combine(end_date, datetime.max.time())
            )
            sync_log.save()
            
            # Get vital type mappings
            vital_type_map = {
                'heart_rate': 'HR',
                'steps': 'STEPS',
                'sleep': 'SLEEP',
                'spo2': 'SPO2'
            }
            
            all_data = []
            
            # Fetch supported data types
            if 'heart_rate' in credential.provider.supported_vitals:
                all_data.extend(client.get_heart_rate(start_date, end_date))
            
            if 'steps' in credential.provider.supported_vitals:
                all_data.extend(client.get_steps(start_date, end_date))
            
            if 'sleep' in credential.provider.supported_vitals:
                all_data.extend(client.get_sleep(start_date, end_date))
            
            if 'spo2' in credential.provider.supported_vitals:
                if hasattr(client, 'get_spo2'):
                    all_data.extend(client.get_spo2(start_date, end_date))
            
            # Process and store data
            created_count = 0
            updated_count = 0
            failed_count = 0
            
            for reading_data in all_data:
                try:
                    # Get vital type
                    vital_code = vital_type_map.get(reading_data['type'])
                    if not vital_code:
                        logger.warning(f"Unknown vital type: {reading_data['type']}")
                        continue
                    
                    vital_type = VitalType.objects.get(code=vital_code, is_active=True)
                    
                    # Parse timestamp
                    measured_at = datetime.fromisoformat(
                        reading_data['timestamp'].replace('Z', '+00:00')
                    )
                    if timezone.is_naive(measured_at):
                        measured_at = timezone.make_aware(measured_at)
                    
                    # Check if reading already exists (avoid duplicates)
                    existing = VitalReading.objects.filter(
                        patient=data_source.patient,
                        vital_type=vital_type,
                        data_source=data_source,
                        measured_at=measured_at
                    ).first()
                    
                    if existing:
                        # Update existing
                        existing.value = reading_data.get('value')
                        existing.save()
                        updated_count += 1
                    else:
                        # Create new reading
                        VitalReading.objects.create(
                            patient=data_source.patient,
                            vital_type=vital_type,
                            data_source=data_source,
                            measured_at=measured_at,
                            value=reading_data.get('value'),
                            unit=vital_type.unit,
                            data_quality='GOOD'
                        )
                        created_count += 1
                
                except Exception as e:
                    logger.error(f"Error processing reading: {str(e)}")
                    failed_count += 1
            
            # Update sync log
            sync_log.records_fetched = len(all_data)
            sync_log.records_created = created_count
            sync_log.records_updated = updated_count
            sync_log.records_failed = failed_count
            sync_log.complete('SUCCESS')
            
            # Update credential
            credential.last_sync_at = timezone.now()
            credential.status = 'ACTIVE'
            credential.save()
            
            # Update data source
            data_source.last_sync_at = timezone.now()
            data_source.save()
            
            logger.info(
                f"Synced {data_source.device_name}: "
                f"{created_count} created, {updated_count} updated, {failed_count} failed"
            )
            
            return {
                'success': True,
                'created': created_count,
                'updated': updated_count,
                'failed': failed_count
            }
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Sync failed for data source {data_source_id}: {error_msg}")
            
            sync_log.complete('FAILED', error_msg)
            
            credential.status = 'ERROR'
            credential.last_error = error_msg
            credential.save()
            
            return {
                'success': False,
                'error': error_msg
            }
    
    except DataSource.DoesNotExist:
        logger.error(f"Data source {data_source_id} not found")
        return {'success': False, 'error': 'Data source not found'}


@shared_task
def refresh_expired_tokens():
    """
    Refresh tokens that are expiring soon
    Run this task hourly
    """
    # Get credentials that need refresh
    threshold = timezone.now() + timedelta(hours=2)
    
    credentials = CloudAPICredential.objects.filter(
        status='ACTIVE',
        expires_at__lte=threshold
    )
    
    refreshed_count = 0
    
    for credential in credentials:
        try:
            # Get appropriate client
            if credential.provider.name == 'FITBIT':
                client = FitbitClient(credential)
            elif credential.provider.name == 'GOOGLE_FIT':
                client = GoogleFitClient(credential)
            else:
                continue
            
            # Attempt refresh
            if client.refresh_token():
                refreshed_count += 1
                logger.info(f"Refreshed token for credential {credential.id}")
            else:
                logger.error(f"Failed to refresh token for credential {credential.id}")
        
        except Exception as e:
            logger.error(f"Error refreshing token for credential {credential.id}: {str(e)}")
    
    logger.info(f"Refreshed {refreshed_count} tokens")
    return refreshed_count


@shared_task
def detect_data_conflicts():
    """
    Detect conflicts when multiple devices report different values
    Run this task every hour
    """
    from django.db.models import Count
    
    # Time window for conflict detection (5 minutes)
    time_window = timedelta(minutes=5)
    
    # Look at readings from last 24 hours
    start_time = timezone.now() - timedelta(hours=24)
    
    # Get patients with multiple devices for same vital type
    from patients.models import PatientProfile
    patients = PatientProfile.objects.filter(is_active=True)
    
    conflicts_detected = 0
    
    for patient in patients:
        # Get all vital types measured by this patient
        vital_types = VitalReading.objects.filter(
            patient=patient,
            measured_at__gte=start_time
        ).values_list('vital_type', flat=True).distinct()
        
        for vital_type_id in vital_types:
            # Get readings grouped by time windows
            readings = VitalReading.objects.filter(
                patient=patient,
                vital_type_id=vital_type_id,
                measured_at__gte=start_time,
                is_deleted=False
            ).order_by('measured_at')
            
            # Group readings by time windows
            time_groups = {}
            for reading in readings:
                # Round to 5-minute windows
                window_start = reading.measured_at.replace(
                    minute=(reading.measured_at.minute // 5) * 5,
                    second=0,
                    microsecond=0
                )
                
                if window_start not in time_groups:
                    time_groups[window_start] = []
                
                time_groups[window_start].append(reading)
            
            # Check for conflicts in each window
            for window_start, window_readings in time_groups.items():
                if len(window_readings) < 2:
                    continue  # No conflict with single reading
                
                # Get different data sources
                sources = set(r.data_source_id for r in window_readings)
                if len(sources) < 2:
                    continue  # Same device, no conflict
                
                # Get values
                values = []
                for r in window_readings:
                    if r.value is not None:
                        values.append(float(r.value))
                
                if len(values) < 2:
                    continue
                
                # Calculate deviation
                max_val = max(values)
                min_val = min(values)
                deviation = max_val - min_val
                avg_val = sum(values) / len(values)
                deviation_pct = (deviation / avg_val * 100) if avg_val > 0 else 0
                
                # Threshold for conflict (10% deviation)
                if deviation_pct > 10:
                    # Create conflict record
                    readings_data = [
                        {
                            'id': r.id,
                            'value': float(r.value) if r.value else None,
                            'source': r.data_source.device_name,
                            'source_id': r.data_source_id,
                            'measured_at': r.measured_at.isoformat()
                        }
                        for r in window_readings
                    ]
                    
                    conflict, created = DataConflict.objects.get_or_create(
                        patient=patient,
                        vital_type_id=vital_type_id,
                        conflict_time=window_start,
                        defaults={
                            'time_window_minutes': 5,
                            'readings': readings_data,
                            'max_deviation': deviation,
                            'deviation_percentage': deviation_pct,
                            'resolution_method': 'PENDING'
                        }
                    )
                    
                    if created:
                        conflicts_detected += 1
                        logger.info(
                            f"Conflict detected for patient {patient.id}, "
                            f"vital type {vital_type_id}: {deviation_pct:.1f}% deviation"
                        )
    
    logger.info(f"Detected {conflicts_detected} new data conflicts")
    return conflicts_detected


@shared_task
def cleanup_old_sync_logs():
    """
    Archive or delete old sync logs
    Run this task daily
    """
    # Keep logs for 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    
    old_logs = DeviceSyncLog.objects.filter(started_at__lt=cutoff_date)
    count = old_logs.count()
    
    # Delete old logs
    old_logs.delete()
    
    logger.info(f"Cleaned up {count} old sync logs")
    return count


@shared_task
def check_device_health():
    """
    Check health of all devices and alert if issues
    Run this task every 6 hours
    """
    # Check for devices that haven't synced in 24 hours
    threshold = timezone.now() - timedelta(hours=24)
    
    stale_devices = DataSource.objects.filter(
        is_active=True,
        source_type='CLOUD_API',
        last_sync_at__lt=threshold
    )
    
    issues = []
    
    for device in stale_devices:
        issues.append({
            'device_id': device.id,
            'device_name': device.device_name,
            'patient_id': device.patient_id,
            'last_sync': device.last_sync_at,
            'issue': 'No sync in 24 hours'
        })
        
        # Could send alert here
        logger.warning(
            f"Device {device.device_name} (ID: {device.id}) "
            f"has not synced in 24+ hours"
        )
    
    # Check for credentials with errors
    error_credentials = CloudAPICredential.objects.filter(
        status='ERROR'
    )
    
    for credential in error_credentials:
        issues.append({
            'device_id': credential.data_source.id if credential.data_source else None,
            'provider': credential.provider.display_name,
            'patient_id': credential.patient_id,
            'issue': credential.last_error
        })
    
    logger.info(f"Device health check found {len(issues)} issues")
    return issues
