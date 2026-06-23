"""
nutrition_utils.py — Pure calculation helpers for nutrition tracking.

No ORM side effects. Used by NutritionMonitorAgent and threshold checks.
Mirrors the pattern of medications/schedule_utils.py.
"""
from datetime import timedelta

from django.db.models import Sum


def get_daily_kcal_total(patient_id: int, date) -> int:
    """Sum of estimated_kcal across all NutritionLog entries on a given date."""
    from .models import NutritionLog
    result = (
        NutritionLog.objects
        .filter(
            patient_id=patient_id,
            meal_time__date=date,
            estimated_kcal__isnull=False,
        )
        .aggregate(total=Sum('estimated_kcal'))['total']
    )
    return result or 0


def get_threshold_kcal(patient) -> int | None:
    """
    Returns the minimum acceptable daily kcal for this patient,
    or None if no calorie target has been set.
    """
    if not patient.daily_calorie_target:
        return None
    return int(
        patient.daily_calorie_target
        * patient.nutrition_alert_threshold_percent
        / 100
    )


def is_below_threshold(patient, date) -> bool:
    """True if the patient's daily total on 'date' is below their threshold."""
    threshold = get_threshold_kcal(patient)
    if threshold is None:
        return False
    return get_daily_kcal_total(patient.id, date) < threshold


def get_consecutive_low_days(patient, up_to_date, window: int = 3) -> int:
    """
    Returns the number of consecutive days, counting back from up_to_date,
    where the daily total was below threshold. Stops counting at the first
    day that is NOT below threshold.
    """
    count = 0
    for i in range(window):
        day = up_to_date - timedelta(days=i)
        if is_below_threshold(patient, day):
            count += 1
        else:
            break
    return count
