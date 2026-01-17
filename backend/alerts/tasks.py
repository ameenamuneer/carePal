from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def create_medication_alert(adherence_id, consecutive_misses):
    """
    Placeholder task for creating medication alerts.
    """
    logger.info(f"Creating alert for adherence {adherence_id} with {consecutive_misses} consecutive misses.")
    # Implementation will be added in Alerts module
    pass
