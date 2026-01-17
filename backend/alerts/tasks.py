from celery import shared_task
from django.utils import timezone
from .models import (
    AlertType, Alert, AlertDelivery, AlertRule,
    NotificationPreference, AlertEscalation, AlertStatistics
)
from patients.models import PatientProfile
from vitals.models import VitalReading
from medications.models import MedicationAdherence
import logging

logger = logging.getLogger(__name__)

@shared_task
def create_vital_alert(vital_reading_id):
    """
    Create an alert for a vital reading anomaly
    """
    try:
        reading = VitalReading.objects.get(id=vital_reading_id)
        
        # Logic to determine if alert is needed would ideally be in a service
        # For now, we assume this task is called when an anomaly is detected
        
        # Find appropriate alert type
        try:
            alert_type = AlertType.objects.get(code='VITAL_ANOMALY')
        except AlertType.DoesNotExist:
            logger.error("Alert type VITAL_ANOMALY not found")
            return
            
        # Create alert
        alert = Alert.objects.create(
            alert_type=alert_type,
            patient=reading.patient,
            severity=alert_type.default_severity,
            title=f"Abnormal {reading.vital_type.name} Reading",
            message=f"Recorded {reading.value} {reading.vital_type.unit}",
            vital_reading=reading,
            context_data={
                'value': reading.value,
                'unit': reading.vital_type.unit,
                'vital_type': reading.vital_type.name
            }
        )
        
        # Process delivery
        process_alert_delivery.delay(alert.id)
        
        return alert.id
    except VitalReading.DoesNotExist:
        logger.error(f"Vital reading {vital_reading_id} not found")
        return None

@shared_task
def create_medication_alert(adherence_id):
    """
    Create an alert for missed medication
    """
    try:
        adherence = MedicationAdherence.objects.get(id=adherence_id)
        
        if adherence.status != 'MISSED':
            return
            
        try:
            alert_type = AlertType.objects.get(code='MEDICATION_MISSED')
        except AlertType.DoesNotExist:
            logger.error("Alert type MEDICATION_MISSED not found")
            return
            
        alert = Alert.objects.create(
            alert_type=alert_type,
            patient=adherence.schedule.patient,
            severity=alert_type.default_severity,
            title=f"Missed Medication: {adherence.schedule.medication.name}",
            message=f"Missed dose scheduled for {adherence.scheduled_time}",
            medication_adherence=adherence,
            context_data={
                'medication': adherence.schedule.medication.name,
                'scheduled_time': str(adherence.scheduled_time)
            }
        )
        
        process_alert_delivery.delay(alert.id)
        
        return alert.id
    except MedicationAdherence.DoesNotExist:
        logger.error(f"Medication adherence {adherence_id} not found")
        return None

@shared_task
def process_alert_delivery(alert_id):
    """
    Determine recipients and channels, then trigger delivery
    """
    try:
        alert = Alert.objects.get(id=alert_id)
        
        if alert.status != 'PENDING':
            logger.warning(f"Alert {alert_id} already processed (status: {alert.status})")
            return
        
        # Get recipients based on alert rules and preferences
        recipients = _get_alert_recipients(alert)
        
        if not recipients:
            logger.warning(f"No recipients found for alert {alert_id}")
            alert.status = 'FAILED'
            alert.metadata['error'] = 'No recipients found'
            alert.save()
            return
        
        # Determine delivery channels
        channels = _get_delivery_channels(alert)
        
        delivery_count = 0
        
        for recipient in recipients:
            # Get user's notification preferences
            try:
                prefs = NotificationPreference.objects.get(user=recipient)
            except NotificationPreference.DoesNotExist:
                # Create default preferences
                prefs = NotificationPreference.objects.create(user=recipient)
            
            # Check if user wants to receive this alert
            if not _should_receive_alert(prefs, alert):
                logger.info(f"User {recipient.id} filtered out alert {alert_id} by preferences")
                continue
            
            # Deliver through each channel
            for channel in channels:
                if _is_channel_enabled(prefs, channel):
                    # Create delivery record
                    delivery = AlertDelivery.objects.create(
                        alert=alert,
                        recipient=recipient,
                        channel=channel,
                        recipient_address=_get_recipient_address(prefs, channel),
                        status='PENDING'
                    )
                    
                    # Trigger actual delivery
                    send_alert_notification.delay(delivery.id)
                    delivery_count += 1
        
        # Update alert status
        if delivery_count > 0:
            alert.status = 'SENT'
            alert.sent_at = timezone.now()
            alert.save()
            
            logger.info(f"Created {delivery_count} deliveries for alert {alert.id}")
        else:
            alert.status = 'FAILED'
            alert.metadata['error'] = 'No deliveries created'
            alert.save()
        
        return delivery_count
    except Alert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found")
        return 0
    except Exception as e:
        logger.error(f"Error processing alert delivery: {str(e)}")
        return 0

@shared_task
def send_alert_notification(delivery_id):
    """
    Send actual notification via provider (Twilio, SendGrid, FCM, etc.)
    """
    try:
        delivery = AlertDelivery.objects.get(id=delivery_id)
        
        logger.info(
            f"Sending alert {delivery.alert.id} to {delivery.recipient.get_full_name()} "
            f"via {delivery.channel}"
        )
        
        # Here you would integrate with actual notification services:
        
        if delivery.channel == 'SMS':
            # Integrate with Twilio, AWS SNS, etc.
            # success = send_sms(delivery.recipient_address, delivery.alert.message)
            success = True  # Simulated for now
            
        elif delivery.channel == 'EMAIL':
            # Integrate with SendGrid, AWS SES, etc.
            # success = send_email(delivery.recipient_address, delivery.alert.title, delivery.alert.message)
            success = True  # Simulated
            
        elif delivery.channel == 'PUSH':
            # Integrate with Firebase Cloud Messaging, APNs, etc.
            # success = send_push_notification(delivery.recipient_address, delivery.alert.title, delivery.alert.message)
            success = True  # Simulated
            
        elif delivery.channel == 'VOICE_CALL':
            # Integrate with Twilio Voice, etc.
            # success = initiate_voice_call(delivery.recipient_address, delivery.alert.message)
            success = True  # Simulated
            
        elif delivery.channel == 'IN_APP':
            # In-app notifications are handled by the frontend
            success = True
        
        else:
            success = False
            delivery.error_message = f"Unsupported channel: {delivery.channel}"
        
        # Update delivery status
        if success:
            delivery.status = 'SENT'
            delivery.sent_at = timezone.now()
            delivery.delivered_at = timezone.now()  # For now, assume immediate delivery
        else:
            delivery.status = 'FAILED'
        
        delivery.save()
        
        return success
    except AlertDelivery.DoesNotExist:
        logger.error(f"Alert delivery {delivery_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending alert notification: {str(e)}")
        
        # Update delivery with error
        try:
            delivery = AlertDelivery.objects.get(id=delivery_id)
            delivery.status = 'FAILED'
            delivery.error_message = str(e)
            delivery.retry_count += 1
            delivery.last_retry_at = timezone.now()
            delivery.save()
        except:
            pass
        
        return False

@shared_task
def check_alert_escalation():
    """
    Periodically check for alerts that need escalation
    """
    alerts = Alert.objects.filter(
        status__in=['PENDING', 'SENT', 'DELIVERED'],
        is_escalated=False
    )
    
    escalated_count = 0
    
    for alert in alerts:
        if alert.needs_escalation:
            escalate_alert.delay(alert.id, reason='Auto-escalation: No acknowledgment within time limit')
            escalated_count += 1
    
    logger.info(f"Triggered escalation for {escalated_count} alerts")
    return escalated_count

@shared_task
def escalate_alert(alert_id, reason='Escalation', manual=False, new_severity=None):
    """
    Escalate an alert
    """
    try:
        alert = Alert.objects.get(id=alert_id)
        
        previous_severity = alert.severity
        
        # Upgrade severity if requested
        if new_severity:
            alert.severity = new_severity
        elif not manual:
            # Auto escalation usually stays same severity or bumps up
            pass
            
        alert.is_escalated = True
        alert.escalated_at = timezone.now()
        alert.escalation_level += 1
        alert.status = 'ESCALATED'
        alert.save()
        
        # Create escalation record
        AlertEscalation.objects.create(
            alert=alert,
            escalation_type='MANUAL' if manual else 'AUTO',
            escalation_level=alert.escalation_level,
            trigger_reason=reason,
            previous_severity=previous_severity,
            new_severity=alert.severity
        )
        
        # Re-process delivery (will notify supervisors/doctors)
        # Note: In a real system, you'd logic to determining NEW recipients for escalation
        # For now, we'll just re-deliver to existing recipients with high priority
        process_alert_delivery.delay(alert.id)
        
        return True
    except Alert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found")
        return False

@shared_task
def expire_old_alerts():
    """
    Mark old unacknowledged alerts as expired
    """
    # Example: Expire unacknowledged info/warning alerts after 7 days
    expiry_time = timezone.now() - timezone.timedelta(days=7)
    
    expired_count = Alert.objects.filter(
        status__in=['PENDING', 'SENT', 'DELIVERED'],
        severity__in=['INFO', 'WARNING'],
        created_at__lt=expiry_time
    ).update(status='EXPIRED')
    
    logger.info(f"Expired {expired_count} old alerts")
    return expired_count

@shared_task
def compute_alert_statistics():
    """
    Compute daily statistics
    """
    # Logic to aggregate alerts and update AlertStatistics model
    # simplified for brevity
    pass

@shared_task
def retry_failed_deliveries():
    """
    Retry failed deliveries
    """
    # Logic to retry failed deliveries
    pass

# Helper functions

def _get_alert_recipients(alert):
    """Get list of users to receive alert"""
    recipients = set()
    
    # Always notify patient if they are a user
    if alert.patient.user:
        recipients.add(alert.patient.user)
    
    # Notify family members linked to patient
    from family.models import FamilyMember
    family_members = FamilyMember.objects.filter(
        patient=alert.patient,
        is_active=True
    )
    
    for fm in family_members:
        recipients.add(fm.user)
        
    return list(recipients)

def _get_delivery_channels(alert):
    """Determine delivery channels"""
    # Use alert type defaults
    return alert.alert_type.default_channels or ['in_app']

def _should_receive_alert(prefs, alert):
    """Check if user wants this alert"""
    if alert.severity == 'INFO' and not prefs.receive_info:
        return False
    if alert.severity == 'WARNING' and not prefs.receive_warning:
        return False
    if alert.severity == 'CRITICAL' and not prefs.receive_critical:
        return False
    if alert.severity == 'EMERGENCY' and not prefs.receive_emergency:
        return False
        
    # Check quiet hours
    if prefs.is_in_quiet_hours(alert.severity):
        return False
        
    return True

def _is_channel_enabled(prefs, channel):
    """Check if user has enacted this channel"""
    if channel == 'IN_APP' and prefs.enable_in_app:
        return True
    if channel == 'PUSH' and prefs.enable_push:
        return True
    if channel == 'SMS' and prefs.enable_sms:
        return True
    if channel == 'EMAIL' and prefs.enable_email:
        return True
    if channel == 'VOICE_CALL' and prefs.enable_voice_call:
        return True
    return False

def _get_recipient_address(prefs, channel):
    """Get address for channel"""
    if channel == 'SMS':
        return prefs.sms_phone_number
    if channel == 'VOICE_CALL':
        return prefs.voice_call_number
    if channel == 'EMAIL':
        return prefs.email_address
    if channel == 'PUSH':
        # Just return first token for now
        return prefs.push_device_tokens[0] if prefs.push_device_tokens else ''
    return ''
