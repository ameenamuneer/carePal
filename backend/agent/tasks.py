import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_medication_log(self, activity_log_id: int):
    try:
        from .models import PatientActivityLog
        log = PatientActivityLog.objects.select_related(
            'patient__user'
        ).get(id=activity_log_id)

        from .medication_monitor_agent import MedicationMonitorAgent
        agent = MedicationMonitorAgent()
        agent.process(log)

    except PatientActivityLog.DoesNotExist:
        logger.warning(f"process_medication_log: log {activity_log_id} not found")
    except Exception as exc:
        logger.error(f"process_medication_log failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_nutrition_log(self, activity_log_id: int):
    """
    Triggered whenever a MEAL activity log is saved.
    Calls NutritionMonitorAgent to parse the description, estimate kcal,
    create a NutritionLog, and reactively check the daily threshold.
    """
    try:
        from .models import PatientActivityLog
        log = PatientActivityLog.objects.select_related(
            'patient__user'
        ).get(id=activity_log_id)

        from .nutrition_monitor_agent import NutritionMonitorAgent
        NutritionMonitorAgent().process(log)

    except PatientActivityLog.DoesNotExist:
        logger.warning(f"process_nutrition_log: log {activity_log_id} not found")
    except Exception as exc:
        logger.error(f"process_nutrition_log failed: {exc}")
        raise self.retry(exc=exc)
