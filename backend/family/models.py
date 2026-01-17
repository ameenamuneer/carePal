from django.db import models
from django.conf import settings
from patients.models import PatientProfile

class FamilyAccess(models.Model):
    class Relation(models.TextChoices):
        CHILD = 'CHILD', 'Child'
        SPOUSE = 'SPOUSE', 'Spouse'
        OTHER = 'OTHER', 'Other'

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='family_access')
    family_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accessible_patients')
    relation = models.CharField(max_length=50, choices=Relation.choices)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('patient', 'family_member')
