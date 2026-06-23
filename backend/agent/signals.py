from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PatientActivityLog


@receiver(post_save, sender=PatientActivityLog)
def on_activity_log_saved(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.activity_type == 'MEDICATION':
        from .tasks import process_medication_log
        process_medication_log.delay(instance.id)
    elif instance.activity_type == 'MEAL':
        from .tasks import process_nutrition_log
        process_nutrition_log.delay(instance.id)
