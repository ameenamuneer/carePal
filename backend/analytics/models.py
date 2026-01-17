from django.db import models
from patients.models import PatientProfile

class DailyHealthSummary(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='daily_summaries')
    date = models.DateField()
    total_steps = models.IntegerField(default=0)
    avg_heart_rate = models.FloatField(null=True, blank=True)
    avg_blood_pressure = models.JSONField(null=True, blank=True)
    sleep_hours = models.FloatField(default=0.0)
    calories_burned = models.FloatField(default=0.0)
    
    class Meta:
        unique_together = ('patient', 'date')
        ordering = ['-date']
