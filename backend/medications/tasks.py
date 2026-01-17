from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Q
from datetime import datetime, timedelta, time
from .models import (
    Medication, MedicationSchedule, MedicationAdherence,
    MedicationEscalation, MedicationAdherencePattern
)
from patients.models import PatientProfile
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_adherence_records(medication_id, days=30):
    """
    Generate adherence records for a medication for the next X days
    Called when medication is created or resumed
    """
    try:
        medication = Medication.objects.get(id=medication_id)
        
        if medication.status != 'ACTIVE':
            logger.info(f"Skipping adherence generation for inactive medication {medication_id}")
            return
        
        start_date = max(timezone.now().date(), medication.start_date)
        end_date = medication.end_date if medication.end_date else start_date + timedelta(days=days)
        
        # Don't generate beyond end_date
        if end_date < start_date:
            return
        
        schedules = MedicationSchedule.objects.filter(
            medication=medication,
            is_active=True
        )
        
        if not schedules.exists():
            logger.warning(f"No schedules found for medication {medication_id}")
            return
        
        created_count = 0
        current_date = start_date
        
        while current_date <= end_date:
            for schedule in schedules:
                # Check if should create for this day
                if schedule.days_of_week and current_date.weekday() not in schedule.days_of_week:
                    continue
                
                # Create scheduled_datetime
                scheduled_datetime = timezone.make_aware(
                    datetime.combine(current_date, schedule.time_of_day)
                )
                
                # Don't create if in the past
                if scheduled_datetime < timezone.now():
                    current_date += timedelta(days=1)
                    continue
                
                # Create adherence record
                adherence, created = MedicationAdherence.objects.get_or_create(
                    medication=medication,
                    scheduled_datetime=scheduled_datetime,
                    defaults={
                        'schedule': schedule,
                        'scheduled_date': current_date,
                        'scheduled_time': schedule.time_of_day,
                        'status': 'SCHEDULED'
                    }
                )
                
                if created:
                    created_count += 1
            
            current_date += timedelta(days=1)
        
        logger.info(f"Generated {created_count} adherence records for medication {medication_id}")
        return created_count
        
    except Medication.DoesNotExist:
        logger.error(f"Medication {medication_id} not found")
        return 0


@shared_task
def regenerate_adherence_records(medication_id):
    """
    Regenerate adherence records after schedule change
    Deletes future scheduled records and recreates them
    """
    try:
        medication = Medication.objects.get(id=medication_id)
        
        # Delete future scheduled adherence records
        deleted_count = MedicationAdherence.objects.filter(
            medication=medication,
            status='SCHEDULED',
            scheduled_datetime__gte=timezone.now()
        ).delete()[0]
        
        logger.info(f"Deleted {deleted_count} future adherence records for medication {medication_id}")
        
        # Generate new ones
        created_count = generate_adherence_records(medication_id, days=30)
        
        return {'deleted': deleted_count, 'created': created_count}
        
    except Medication.DoesNotExist:
        logger.error(f"Medication {medication_id} not found")
        return {'deleted': 0, 'created': 0}


@shared_task
def send_medication_reminders():
    """
    Send medication reminders for upcoming doses
    Run this task every 5 minutes
    """
    now = timezone.now()
    reminder_window = now + timedelta(minutes=15)  # Remind 15 minutes before
    
    # Get scheduled adherence records in the reminder window
    upcoming = MedicationAdherence.objects.filter(
        status='SCHEDULED',
        scheduled_datetime__gte=now,
        scheduled_datetime__lte=reminder_window,
        schedule__reminder_enabled=True
    ).select_related('medication', 'schedule')
    
    # Filter out those already reminded
    to_remind = [
        adh for adh in upcoming 
        if not adh.reminder_sent_at or 
        (now - adh.reminder_sent_at).total_seconds() > 3600  # Don't re-remind within 1 hour
    ]
    
    reminder_count = 0
    
    for adherence in to_remind:
        try:
            # Here you would integrate with:
            # - Voice assistant to announce reminder
            # - Push notification service
            # - SMS service
            
            # For now, just log and update
            logger.info(
                f"Reminder: {adherence.medication.medication_name} "
                f"for patient {adherence.medication.patient.user.get_full_name()} "
                f"at {adherence.scheduled_time}"
            )
            
            adherence.reminder_sent_at = now
            adherence.reminder_count += 1
            adherence.save()
            
            reminder_count += 1
            
        except Exception as e:
            logger.error(f"Error sending reminder for adherence {adherence.id}: {str(e)}")
    
    logger.info(f"Sent {reminder_count} medication reminders")
    return reminder_count


@shared_task
def check_missed_medications():
    """
    Check for missed medications and trigger escalation
    Run this task every 30 minutes
    """
    now = timezone.now()
    grace_period = timedelta(hours=1)  # 1 hour grace period
    
    # Find adherence records that are overdue (past scheduled time + grace period)
    overdue = MedicationAdherence.objects.filter(
        status='SCHEDULED',
        scheduled_datetime__lt=now - grace_period
    ).select_related('medication')
    
    for adherence in overdue:
        # Mark as missed
        adherence.status = 'MISSED'
        adherence.miss_reason = 'Automatically marked as missed after grace period'
        adherence.save()
        
        # Check if this is a critical medication
        if adherence.medication.is_critical:
            # Trigger immediate escalation
            escalate_missed_medication.delay(adherence.id)
        else:
            # Check for consecutive misses
            check_consecutive_misses.delay(adherence.medication.id)
    
    logger.info(f"Marked {overdue.count()} medications as missed")
    return overdue.count()


@shared_task
def escalate_missed_medication(adherence_id):
    """
    Escalate a missed critical medication
    """
    try:
        adherence = MedicationAdherence.objects.get(id=adherence_id)
        medication = adherence.medication
        patient = medication.patient
        
        # Count consecutive misses
        consecutive_misses = MedicationAdherence.objects.filter(
            medication=medication,
            status='MISSED',
            scheduled_datetime__lte=adherence.scheduled_datetime
        ).order_by('-scheduled_datetime').count()
        
        # Escalation steps based on consecutive misses
        if consecutive_misses == 1:
            # First miss: Send repeated reminders
            action = 'REMINDER_SENT'
            action_details = {
                'method': 'voice_and_app',
                'message': f'Please take your {medication.medication_name} medication'
            }
            
        elif consecutive_misses == 2:
            # Second miss: Notify family
            action = 'FAMILY_NOTIFIED'
            action_details = {
                'contacts_notified': 'primary_emergency_contact',
                'message': f'Patient has missed {medication.medication_name} medication twice'
            }
            
        elif consecutive_misses >= 3:
            # Third+ miss: Notify doctor and initiate call
            action = 'DOCTOR_NOTIFIED'
            action_details = {
                'doctor_notified': medication.prescribed_by,
                'call_initiated': True,
                'message': f'Critical: Patient has missed {medication.medication_name} {consecutive_misses} times'
            }
        
        # Create escalation record
        escalation = MedicationEscalation.objects.create(
            adherence_record=adherence,
            medication=medication,
            action_taken=action,
            action_details=action_details,
            escalation_reason=f'Missed critical medication: {medication.medication_name}',
            consecutive_misses=consecutive_misses,
            successful=True  # Would be updated based on actual notification success
        )
        
        # Also create an alert
        from alerts.tasks import create_medication_alert
        create_medication_alert.delay(adherence_id, consecutive_misses)
        
        logger.info(
            f"Escalated missed medication for patient {patient.user.get_full_name()}, "
            f"action: {action}, consecutive misses: {consecutive_misses}"
        )
        
        return escalation.id
        
    except MedicationAdherence.DoesNotExist:
        logger.error(f"Adherence record {adherence_id} not found")
        return None


@shared_task
def check_consecutive_misses(medication_id):
    """
    Check for consecutive misses and escalate if needed
    """
    try:
        medication = Medication.objects.get(id=medication_id)
        
        # Get recent adherence records
        recent = MedicationAdherence.objects.filter(
            medication=medication,
            scheduled_datetime__gte=timezone.now() - timedelta(days=7)
        ).order_by('-scheduled_datetime')
        
        # Count consecutive misses from most recent
        consecutive_misses = 0
        for record in recent:
            if record.status == 'MISSED':
                consecutive_misses += 1
            else:
                break
        
        # Escalate if 3+ consecutive misses
        if consecutive_misses >= 3:
            latest_missed = recent.first()
            escalate_missed_medication.delay(latest_missed.id)
        
        return consecutive_misses
        
    except Medication.DoesNotExist:
        logger.error(f"Medication {medication_id} not found")
        return 0


@shared_task
def compute_adherence_patterns():
    """
    Compute adherence patterns for all active medications
    Run this task daily
    """
    patients = PatientProfile.objects.filter(is_active=True)
    
    periods = [
        ('last_7days', timedelta(days=7)),
        ('last_30days', timedelta(days=30))
    ]
    
    patterns_created = 0
    
    for patient in patients:
        # Get all medications (current and past)
        medications = Medication.objects.filter(patient=patient)
        
        for medication in medications:
            for period_label, period_delta in periods:
                try:
                    pattern_count = _compute_pattern_for_medication(
                        patient, medication, period_label, period_delta
                    )
                    patterns_created += pattern_count
                except Exception as e:
                    logger.error(
                        f"Error computing pattern for patient {patient.id}, "
                        f"medication {medication.id}: {str(e)}"
                    )
        
        # Also compute overall patient adherence (all medications combined)
        for period_label, period_delta in periods:
            try:
                _compute_pattern_for_patient(patient, period_label, period_delta)
                patterns_created += 1
            except Exception as e:
                logger.error(f"Error computing overall pattern for patient {patient.id}: {str(e)}")
    
    logger.info(f"Computed {patterns_created} adherence patterns")
    return patterns_created


def _compute_pattern_for_medication(patient, medication, period_label, period_delta):
    """Helper function to compute pattern for a specific medication"""
    end_date = timezone.now().date()
    start_date = end_date - period_delta
    
    # Get adherence records for this period
    records = MedicationAdherence.objects.filter(
        medication=medication,
        scheduled_date__gte=start_date,
        scheduled_date__lte=end_date
    )
    
    if not records.exists():
        return 0
    
    # Calculate statistics
    total_scheduled = records.count()
    total_taken = records.filter(status='TAKEN').count()
    total_missed = records.filter(status='MISSED').count()
    total_skipped = records.filter(status='SKIPPED').count()
    
    adherence_rate = (total_taken / total_scheduled * 100) if total_scheduled > 0 else 0
    
    # Find most missed time
    missed_by_time = {}
    for record in records.filter(status='MISSED'):
        time_key = record.scheduled_time.strftime('%H:%M')
        missed_by_time[time_key] = missed_by_time.get(time_key, 0) + 1
    
    most_missed_time = None
    if missed_by_time:
        most_missed_time_str = max(missed_by_time, key=missed_by_time.get)
        most_missed_time = datetime.strptime(most_missed_time_str, '%H:%M').time()
    
    # Find most missed day
    missed_by_day = {}
    for record in records.filter(status='MISSED'):
        day = record.scheduled_date.weekday()
        missed_by_day[day] = missed_by_day.get(day, 0) + 1
    
    most_missed_day = max(missed_by_day, key=missed_by_day.get) if missed_by_day else None
    
    # Calculate consecutive misses
    consecutive_misses_max = 0
    current_streak = 0
    for record in records.order_by('scheduled_datetime'):
        if record.status == 'MISSED':
            current_streak += 1
            consecutive_misses_max = max(consecutive_misses_max, current_streak)
        else:
            current_streak = 0
    
    # Calculate average delay
    delays = []
    for record in records.filter(status='TAKEN', actual_datetime__isnull=False):
        delay = record.delay_minutes
        if delay and delay > 0:
            delays.append(delay)
    
    average_delay_minutes = sum(delays) / len(delays) if delays else None
    
    # Generate insights
    insights = _generate_adherence_insights(
        adherence_rate, total_missed, consecutive_misses_max,
        most_missed_time, most_missed_day, average_delay_minutes
    )
    
    # Generate recommendations
    recommendations = _generate_adherence_recommendations(
        adherence_rate, most_missed_time, most_missed_day, average_delay_minutes
    )
    
    # Create or update pattern
    pattern, created = MedicationAdherencePattern.objects.update_or_create(
        patient=patient,
        medication=medication,
        period_label=period_label,
        period_start=start_date,
        defaults={
            'period_end': end_date,
            'total_scheduled': total_scheduled,
            'total_taken': total_taken,
            'total_missed': total_missed,
            'total_skipped': total_skipped,
            'adherence_rate': adherence_rate,
            'most_missed_time': most_missed_time,
            'most_missed_day': most_missed_day,
            'consecutive_misses_max': consecutive_misses_max,
            'average_delay_minutes': average_delay_minutes,
            'insights': insights,
            'recommendations': recommendations
        }
    )
    
    return 1 if created else 0


def _compute_pattern_for_patient(patient, period_label, period_delta):
    """Compute overall adherence pattern for patient (all medications)"""
    end_date = timezone.now().date()
    start_date = end_date - period_delta
    
    # Get all adherence records for patient
    records = MedicationAdherence.objects.filter(
        medication__patient=patient,
        scheduled_date__gte=start_date,
        scheduled_date__lte=end_date
    )
    
    if not records.exists():
        return
    
    # Calculate statistics (same as medication-specific)
    total_scheduled = records.count()
    total_taken = records.filter(status='TAKEN').count()
    total_missed = records.filter(status='MISSED').count()
    total_skipped = records.filter(status='SKIPPED').count()
    
    adherence_rate = (total_taken / total_scheduled * 100) if total_scheduled > 0 else 0
    
    # Generate insights
    insights = [
        f"Overall adherence rate: {adherence_rate:.1f}%",
        f"Total medications tracked: {records.values('medication').distinct().count()}",
        f"Doses taken: {total_taken}/{total_scheduled}",
        f"Doses missed: {total_missed}"
    ]
    
    if adherence_rate >= 80:
        insights.append("✓ Good medication adherence")
    elif adherence_rate >= 60:
        insights.append("⚠ Fair adherence - improvement needed")
    else:
        insights.append("⚠ Poor adherence - immediate attention required")
    
    # Create or update pattern (medication=None for overall)
    MedicationAdherencePattern.objects.update_or_create(
        patient=patient,
        medication=None,
        period_label=period_label,
        period_start=start_date,
        defaults={
            'period_end': end_date,
            'total_scheduled': total_scheduled,
            'total_taken': total_taken,
            'total_missed': total_missed,
            'total_skipped': total_skipped,
            'adherence_rate': adherence_rate,
            'insights': insights,
            'recommendations': []
        }
    )


def _generate_adherence_insights(adherence_rate, total_missed, consecutive_misses_max,
                                 most_missed_time, most_missed_day, average_delay_minutes):
    """Generate insights about adherence patterns"""
    insights = []
    
    # Adherence rate insight
    if adherence_rate >= 80:
        insights.append(f"Excellent adherence rate: {adherence_rate:.1f}%")
    elif adherence_rate >= 60:
        insights.append(f"Fair adherence rate: {adherence_rate:.1f}% - improvement recommended")
    else:
        insights.append(f"Poor adherence rate: {adherence_rate:.1f}% - intervention needed")
    
    # Missed doses insight
    if total_missed > 0:
        insights.append(f"{total_missed} doses missed during this period")
    
    # Consecutive misses insight
    if consecutive_misses_max >= 3:
        insights.append(f"⚠ Maximum consecutive misses: {consecutive_misses_max} - concerning pattern")
    
    # Time pattern insight
    if most_missed_time:
        insights.append(f"Most frequently missed time: {most_missed_time.strftime('%I:%M %p')}")
    
    # Day pattern insight
    if most_missed_day is not None:
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        insights.append(f"Most frequently missed day: {days[most_missed_day]}")
    
    # Delay insight
    if average_delay_minutes and average_delay_minutes > 30:
        insights.append(f"Average delay when taken late: {int(average_delay_minutes)} minutes")
    
    return insights


def _generate_adherence_recommendations(adherence_rate, most_missed_time,
                                        most_missed_day, average_delay_minutes):
    """Generate recommendations to improve adherence"""
    recommendations = []
    
    if adherence_rate < 80:
        recommendations.append("Consider setting additional reminders for medication times")
    
    if most_missed_time:
        recommendations.append(
            f"Adjust schedule for {most_missed_time.strftime('%I:%M %p')} doses - "
            "this is your most frequently missed time"
        )
    
    if most_missed_day is not None:
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        recommendations.append(
            f"Pay extra attention on {days[most_missed_day]}s - "
            "this is when you miss most frequently"
        )
    
    if average_delay_minutes and average_delay_minutes > 30:
        recommendations.append(
            "Consider adjusting medication times to better fit your daily routine"
        )
    
    return recommendations


@shared_task
def check_refill_needs():
    """
    Check medications that need refills and notify
    Run this task daily
    """
    active_medications = Medication.objects.filter(status='ACTIVE')
    
    needs_refill = [med for med in active_medications if med.needs_refill]
    
    notification_count = 0
    
    for medication in needs_refill:
        # Check if refill request already exists
        existing_request = MedicationRefill.objects.filter(
            medication=medication,
            status__in=['REQUESTED', 'APPROVED', 'FILLED']
        ).exists()
        
        if not existing_request:
            # Here you would send notification to patient/family
            logger.info(
                f"Refill needed for {medication.medication_name} "
                f"for patient {medication.patient.user.get_full_name()}"
            )
            notification_count += 1
    
    logger.info(f"Sent {notification_count} refill notifications")
    return notification_count
