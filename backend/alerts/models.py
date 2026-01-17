from django.db import models
from patients.models import PatientProfile

class Alert(models.Model):
    class Severity(models.TextChoices):
        INFO = 'INFO', 'Info'
        WARNING = 'WARNING', 'Warning'
        CRITICAL = 'CRITICAL', 'Critical'

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='alerts')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.severity}: {self.message}"
