"""
Dynamic medication schedule calculation.

No MedicationSchedule DB rows needed.
Derive all dose times from Medication.frequency alone.
"""

from datetime import date, time, datetime
from django.db import models as django_models
from django.utils import timezone

# ---------------------------------------------------------------------------
# Frequency → (time_str, label) mappings
# ---------------------------------------------------------------------------
FREQUENCY_TIMES: dict[str, list[tuple[str, str]]] = {
    'ONCE_DAILY':        [('08:00', 'Morning')],
    'TWICE_DAILY':       [('08:00', 'Morning'), ('20:00', 'Evening')],
    'THREE_TIMES_DAILY': [('08:00', 'Morning'), ('13:00', 'Afternoon'), ('20:00', 'Evening')],
    'FOUR_TIMES_DAILY':  [('07:00', 'Morning'), ('12:00', 'Noon'), ('17:00', 'Afternoon'), ('22:00', 'Night')],
    'EVERY_4_HOURS':     [('06:00', '6 AM'), ('10:00', '10 AM'), ('14:00', '2 PM'),
                          ('18:00', '6 PM'), ('22:00', '10 PM')],
    'EVERY_6_HOURS':     [('06:00', '6 AM'), ('12:00', 'Noon'), ('18:00', '6 PM'), ('00:00', 'Midnight')],
    'EVERY_8_HOURS':     [('06:00', '6 AM'), ('14:00', '2 PM'), ('22:00', '10 PM')],
    'EVERY_12_HOURS':    [('08:00', 'Morning'), ('20:00', 'Evening')],
    'WEEKLY':            [('08:00', 'Morning')],
    'TWICE_WEEKLY':      [('08:00', 'Morning')],
    'MONTHLY':           [('08:00', 'Morning')],
    'AS_NEEDED':         [],           # no fixed schedule; excluded from auto-schedule
}


def _parse_time(time_str: str) -> time:
    h, m = map(int, time_str.split(':'))
    return time(h, m)


def get_times_for_frequency(frequency: str) -> list[tuple[time, str]]:
    """Return default (time, label) list for a given frequency code."""
    raw = FREQUENCY_TIMES.get(frequency, [('08:00', 'Morning')])
    return [(_parse_time(ts), label) for ts, label in raw]


def get_times_for_medication(medication) -> list[tuple[time, str]]:
    """
    Return (time, label) pairs for a medication.

    Priority:
      1. medication.dose_times  — patient-specific preference stored on the model
      2. frequency default      — fallback when dose_times is empty/unset
    """
    if medication.dose_times:
        return [(_parse_time(entry['time']), entry.get('label', '')) for entry in medication.dose_times]
    return get_times_for_frequency(medication.frequency)


def default_dose_times_for_frequency(frequency: str) -> list[dict]:
    """Return dose_times JSON value (list of dicts) for a frequency.  Used on medication create."""
    return [{'time': ts, 'label': label} for ts, label in FREQUENCY_TIMES.get(frequency, [('08:00', 'Morning')])]


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def get_schedule_for_date(patient_id: int, target_date: date) -> list[dict]:
    """
    Pure calculation — no writes.

    Returns a list of dose dicts for every active medication on target_date,
    ordered by scheduled_time.  Each dict has:
        medication_id, medication_name, dosage, form, instructions,
        is_critical, frequency, scheduled_time (time obj), time_label, date

    Uses medication.dose_times (patient preference) if set, else frequency default.
    """
    from .models import Medication

    medications = Medication.objects.filter(
        patient_id=patient_id,
        status='ACTIVE',
        start_date__lte=target_date,
    ).filter(
        django_models.Q(end_date__isnull=True) | django_models.Q(end_date__gte=target_date)
    ).order_by('medication_name')

    schedule: list[dict] = []
    for med in medications:
        for t, label in get_times_for_medication(med):
            schedule.append({
                'medication_id': med.id,
                'medication_name': med.medication_name,
                'dosage': med.dosage,
                'form': med.form,
                'instructions': med.instructions or '',
                'is_critical': med.is_critical,
                'frequency': med.frequency,
                'scheduled_time': t,
                'time_label': label,
                'date': target_date,
            })

    schedule.sort(key=lambda x: x['scheduled_time'])
    return schedule


def ensure_adherence_records(patient_id: int, target_date: date) -> list[tuple[dict, object]]:
    """
    Idempotent — safe to call on every request.

    For every calculated dose on target_date, ensure a MedicationAdherence
    row exists (get_or_create).  Returns list of (schedule_item, adherence_record).

    Past records are never modified — only rows with status='SCHEDULED' that
    don't yet exist will be created.
    """
    from .models import MedicationAdherence

    items = get_schedule_for_date(patient_id, target_date)  # uses dose_times if set
    result: list[tuple[dict, object]] = []

    for item in items:
        t = item['scheduled_time']
        scheduled_dt = timezone.make_aware(datetime.combine(target_date, t))

        record, _ = MedicationAdherence.objects.get_or_create(
            medication_id=item['medication_id'],
            scheduled_date=target_date,
            scheduled_time=t,
            defaults={
                'scheduled_datetime': scheduled_dt,
                'status': 'SCHEDULED',
                'schedule': None,       # no MedicationSchedule row needed
            },
        )
        result.append((item, record))

    return result
