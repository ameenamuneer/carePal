"""
Appointment models
Stores appointments booked via Eka.Care in CarePAL database
"""

from django.db import models
from patients.models import PatientProfile


class Appointment(models.Model):
    """
    Appointments stored in CarePAL database
    Booked via Eka.Care API but stored locally for:
    - Offline access
    - Data ownership
    - Performance
    """
    
    # CarePAL reference
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    
    # Eka.Care references
    eka_appointment_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Eka.Care appointment ID"
    )
    eka_doctor_id = models.CharField(max_length=100)
    eka_clinic_id = models.CharField(max_length=100)
    
    # Appointment details
    doctor_name = models.CharField(max_length=200)
    clinic_name = models.CharField(max_length=200)
    appointment_date = models.DateTimeField()
    
    # Mode
    MODE_CHOICES = [
        ('INCLINIC', 'In-Clinic Visit'),
        ('ONLINE', 'Online Consultation'),
    ]
    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default='INCLINIC'
    )
    
    # Status
    STATUS_CHOICES = [
        ('BOOKED', 'Booked'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='BOOKED'
    )
    
    # Metadata
    booking_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Store full Eka.Care response and additional data"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-appointment_date']
        indexes = [
            models.Index(fields=['patient', 'appointment_date']),
            models.Index(fields=['status', 'appointment_date']),
        ]
    
    def __str__(self):
        return f"{self.doctor_name} - {self.appointment_date}"
    
    @property
    def is_upcoming(self):
        from django.utils import timezone
        return self.appointment_date > timezone.now()
    
    @property
    def is_past(self):
        from django.utils import timezone
        return self.appointment_date < timezone.now()
