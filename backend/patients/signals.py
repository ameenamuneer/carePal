from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import User
from .models import PatientProfile

@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    """
    Automatically create a PatientProfile when a User with user_type='PATIENT' is created.
    """
    if created and instance.user_type == 'PATIENT':
        # Check if profile already exists (just in case)
        if not hasattr(instance, 'patient_profile'):
            PatientProfile.objects.create(user=instance)
