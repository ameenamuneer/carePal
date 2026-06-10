# backend/medications/tasks.py
# AI-AGENT-FRIENDLY: Minimal periodic tasks, AI handles the rest

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
from .models import (
    Medication, MedicationAdherence
)
import logging

logger = logging.getLogger(__name__)


# ==================== SINGLE PERIODIC TASK ====================

@shared_task
def prepare_next_day_medications():
    """
    🎯 ONLY PERIODIC TASK - Prepares tomorrow's medication records
    
    Why just this one?
    - AI agent handles real-time checking
    - AI agent marks status changes
    - AI agent sends reminders conversationally
    - This just ensures data exists for tomorrow
    
    Run: Daily at 00:00 (midnight)
    """
    tomorrow = timezone.now().date() + timedelta(days=1)
    
    logger.info(f"[MEDICATION] Preparing records for {tomorrow}")
    
    # Get all active medications that should have doses tomorrow
    from .schedule_utils import get_times_for_medication

    active_meds = Medication.objects.filter(
        status='ACTIVE',
        start_date__lte=tomorrow
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=tomorrow)
    )

    created_count = 0
    skipped_count = 0

    for medication in active_meds:
        times = get_times_for_medication(medication)  # uses dose_times if set
        if not times:
            skipped_count += 1
            continue

        for t, _label in times:
            scheduled_datetime = timezone.make_aware(datetime.combine(tomorrow, t))
            _record, created = MedicationAdherence.objects.get_or_create(
                medication=medication,
                scheduled_date=tomorrow,
                scheduled_time=t,
                defaults={
                    'scheduled_datetime': scheduled_datetime,
                    'status': 'SCHEDULED',
                    'schedule': None,
                },
            )
            if created:
                created_count += 1
    
    logger.info(
        f"[MEDICATION] Prepared {created_count} records for {tomorrow}, "
        f"skipped {skipped_count} (day-of-week filtered)"
    )
    
    return {
        'date': tomorrow.isoformat(),
        'created': created_count,
        'skipped': skipped_count
    }


# ==================== ON-DEMAND TASKS ====================

@shared_task
def generate_adherence_records(medication_id, days=7):
    """
    Pre-generate adherence records for a medication over the next N days.

    Uses the dynamic schedule (frequency → times) — no MedicationSchedule rows needed.
    get_or_create is used so re-running is always safe and past records are untouched.

    Called when:
    - Medication created (via views.py)
    - Medication frequency/dates updated (regenerate_adherence_records)
    - AI agent requests historical backfill
    """
    from .schedule_utils import get_times_for_medication

    try:
        medication = Medication.objects.get(id=medication_id)

        if medication.status != 'ACTIVE':
            logger.info(f"[MEDICATION] Skipping inactive medication {medication_id}")
            return 0

        today = timezone.now().date()
        start_date = max(today, medication.start_date)

        if medication.end_date:
            end_date = min(medication.end_date, start_date + timedelta(days=days))
        else:
            end_date = start_date + timedelta(days=days)

        if end_date < start_date:
            return 0

        times = get_times_for_medication(medication)  # uses dose_times if set
        if not times:
            # AS_NEEDED or unknown frequency — no fixed schedule to generate
            logger.info(f"[MEDICATION] No fixed times for frequency '{medication.frequency}' on med {medication_id}")
            return 0

        created_count = 0
        current_date = start_date

        while current_date <= end_date:
            for t, _label in times:
                scheduled_dt = timezone.make_aware(datetime.combine(current_date, t))
                _record, created = MedicationAdherence.objects.get_or_create(
                    medication=medication,
                    scheduled_date=current_date,
                    scheduled_time=t,
                    defaults={
                        'scheduled_datetime': scheduled_dt,
                        'status': 'SCHEDULED',
                        'schedule': None,
                    },
                )
                if created:
                    created_count += 1
            current_date += timedelta(days=1)

        logger.info(
            f"[MEDICATION] Pre-generated {created_count} adherence records "
            f"for medication {medication_id} ({start_date} to {end_date})"
        )
        return created_count

    except Medication.DoesNotExist:
        logger.error(f"[MEDICATION] Medication {medication_id} not found")
        return 0


@shared_task
def regenerate_adherence_records(medication_id):
    """
    Regenerate adherence records after schedule change
    
    Called when:
    - Medication schedule updated
    - Medication resumed
    
    AI agent will handle immediate status updates
    """
    try:
        medication = Medication.objects.get(id=medication_id)
        today = timezone.now().date()
        
        # Delete FUTURE scheduled records only
        deleted_count = MedicationAdherence.objects.filter(
            medication=medication,
            status='SCHEDULED',
            scheduled_date__gt=today
        ).delete()[0]
        
        logger.info(
            f"[MEDICATION] Deleted {deleted_count} future records for medication {medication_id}"
        )
        
        # Generate next 7 days (including today if needed)
        created_count = generate_adherence_records(medication_id, days=7)
        
        return {
            'deleted': deleted_count,
            'created': created_count
        }
        
    except Medication.DoesNotExist:
        logger.error(f"[MEDICATION] Medication {medication_id} not found")
        return {'deleted': 0, 'created': 0}


# ==================== AI AGENT HELPER TASKS ====================

@shared_task
def ai_batch_mark_missed(adherence_ids, reason='AI agent marked as missed'):
    """
    Batch mark multiple adherence records as missed
    
    Called by AI agent when detecting overdue medications
    More efficient than individual updates
    """
    updated = MedicationAdherence.objects.filter(
        id__in=adherence_ids,
        status='SCHEDULED'
    ).update(
        status='MISSED',
        miss_reason=reason
    )
    
    logger.info(f"[MEDICATION] AI agent marked {updated} medications as missed")
    return updated


@shared_task
def ai_compute_adherence_summary(patient_id, days=7):
    """
    Compute adherence summary for AI agent context
    
    Called on-demand when AI needs to discuss adherence with patient
    """
    from patients.models import PatientProfile
    
    try:
        patient = PatientProfile.objects.get(id=patient_id)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        adherence_records = MedicationAdherence.objects.filter(
            medication__patient=patient,
            scheduled_date__gte=start_date,
            scheduled_date__lte=end_date
        )
        
        total = adherence_records.count()
        if total == 0:
            return {
                'patient_id': patient_id,
                'period_days': days,
                'total': 0,
                'rate': 0,
                'performance': 'no_data'
            }
        
        taken = adherence_records.filter(status='TAKEN').count()
        missed = adherence_records.filter(status='MISSED').count()
        skipped = adherence_records.filter(status='SKIPPED').count()
        
        rate = round((taken / total) * 100, 1)
        
        # Performance categorization for AI agent
        if rate >= 90:
            performance = 'excellent'
        elif rate >= 80:
            performance = 'good'
        elif rate >= 70:
            performance = 'needs_improvement'
        else:
            performance = 'poor'
        
        return {
            'patient_id': patient_id,
            'period_days': days,
            'total': total,
            'taken': taken,
            'missed': missed,
            'skipped': skipped,
            'rate': rate,
            'performance': performance
        }
        
    except PatientProfile.DoesNotExist:
        logger.error(f"[MEDICATION] Patient {patient_id} not found")
        return None


# ==================== LEGACY COMPATIBILITY ====================
# Keep these for backward compatibility during transition

@shared_task
def send_medication_reminders():
    """
    DEPRECATED: AI agent handles reminders conversationally
    
    Keep for backward compatibility during migration
    Will be removed in next version
    """
    logger.warning(
        "[MEDICATION] send_medication_reminders is deprecated. "
        "AI agent now handles reminders."
    )
    return 0


@shared_task
def check_missed_medications():
    """
    DEPRECATED: AI agent checks and marks missed medications
    
    Keep for backward compatibility during migration
    Will be removed in next version
    """
    logger.warning(
        "[MEDICATION] check_missed_medications is deprecated. "
        "AI agent now handles status updates."
    )
    return 0


@shared_task
def compute_adherence_patterns():
    """
    DEPRECATED: AI agent computes on-demand
    
    Keep for backward compatibility
    Will be removed in next version
    """
    logger.warning(
        "[MEDICATION] compute_adherence_patterns is deprecated. "
        "AI agent computes on-demand using ai_compute_adherence_summary."
    )
    return 0
