from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import (
    FamilyMember, FamilyInvitation, CareSchedule,
    FamilyCommunication
)
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_care_schedule_reminders():
    """
    Send reminders for upcoming care schedules
    Run this task every 15 minutes
    """
    now = timezone.now()
    
    # Get schedules that need reminders in the next hour
    upcoming = CareSchedule.objects.filter(
        status='SCHEDULED',
        send_reminder=True,
        reminder_sent=False,
        scheduled_date=now.date()
    )
    
    reminder_count = 0
    
    for schedule in upcoming:
        # Calculate when to send reminder
        scheduled_datetime = timezone.make_aware(
            timezone.datetime.combine(
                schedule.scheduled_date,
                schedule.scheduled_time or timezone.datetime.min.time()
            )
        )
        
        reminder_time = scheduled_datetime - timedelta(
            minutes=schedule.reminder_minutes_before
        )
        
        # Send if it's time
        if now >= reminder_time and now < scheduled_datetime:
            # Send notification to assigned family member
            try:
                # Here you would integrate with notification service
                logger.info(
                    f"Reminder: {schedule.title} for "
                    f"{schedule.assigned_to.user.get_full_name()}"
                )
                
                # Mark as sent
                schedule.reminder_sent = True
                schedule.save()
                
                reminder_count += 1
            except Exception as e:
                logger.error(f"Error sending care schedule reminder: {str(e)}")
    
    logger.info(f"Sent {reminder_count} care schedule reminders")
    return reminder_count


@shared_task
def expire_old_invitations():
    """
    Mark expired invitations
    Run this task daily
    """
    now = timezone.now()
    
    expired = FamilyInvitation.objects.filter(
        expires_at__lte=now,
        status='PENDING'
    )
    
    count = expired.update(status='EXPIRED')
    
    logger.info(f"Marked {count} invitations as expired")
    return count


@shared_task
def check_overdue_schedules():
    """
    Check for overdue care schedules and notify
    Run this task every hour
    """
    now = timezone.now()
    
    overdue = CareSchedule.objects.filter(
        status='SCHEDULED',
        scheduled_date__lt=now.date()
    )
    
    # Also check today's schedules that are past time
    today_overdue = CareSchedule.objects.filter(
        status='SCHEDULED',
        scheduled_date=now.date(),
        scheduled_time__lt=now.time()
    )
    
    all_overdue = list(overdue) + list(today_overdue)
    
    for schedule in all_overdue:
        # Mark as missed
        schedule.status = 'MISSED'
        schedule.save()
        
        # Notify assigned person
        logger.warning(
            f"Missed care schedule: {schedule.title} "
            f"for {schedule.patient.user.get_full_name()}"
        )
    
    logger.info(f"Marked {len(all_overdue)} schedules as missed")
    return len(all_overdue)


@shared_task
def send_daily_family_summary():
    """
    Send daily summary to family members who opted in
    Run this task at configured times
    """
    from .models import FamilyDashboardSettings
    
    current_time = timezone.now().time()
    
    # Get family members who want daily summary at this time
    settings_list = FamilyDashboardSettings.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time=current_time
    ).select_related('family_member__user', 'family_member__patient__user')
    
    summary_count = 0
    
    for settings_obj in settings_list:
        family_member = settings_obj.family_member
        patient = family_member.patient
        
        # Gather summary data
        from alerts.models import Alert
        from medications.models import MedicationAdherence
        
        yesterday = timezone.now() - timedelta(days=1)
        
        # Yesterday's alerts
        alerts_count = Alert.objects.filter(
            patient=patient,
            created_at__gte=yesterday
        ).count()
        
        # Yesterday's medication adherence
        adherence = MedicationAdherence.objects.filter(
            medication__patient=patient,
            scheduled_date=yesterday.date()
        )
        
        taken = adherence.filter(status='TAKEN').count()
        total = adherence.count()
        adherence_rate = (taken / total * 100) if total > 0 else 0
        
        # Prepare email
        try:
            send_mail(
                subject=f"Daily Health Summary for {patient.user.get_full_name()}",
                message=f"""
Hi {family_member.user.get_full_name()},

Here's your daily summary for {patient.user.get_full_name()}:

Alerts: {alerts_count} new alerts
Medication Adherence: {adherence_rate:.1f}% ({taken}/{total} doses taken)

View full details at: {settings.FRONTEND_URL}/family/dashboard?patient_id={patient.id}

Best regards,
CarePAL Team
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[family_member.user.email],
                fail_silently=False,
            )
            
            summary_count += 1
        except Exception as e:
            logger.error(f"Error sending daily summary: {str(e)}")
    
    logger.info(f"Sent {summary_count} daily summaries")
    return summary_count


@shared_task
def cleanup_old_activity_logs():
    """
    Archive or delete old activity logs
    Run this task weekly
    """
    from .models import FamilyActivityLog
    
    # Keep logs for 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    
    old_logs = FamilyActivityLog.objects.filter(created_at__lt=cutoff_date)
    count = old_logs.count()
    
    old_logs.delete()
    
    logger.info(f"Cleaned up {count} old activity logs")
    return count
