from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class User(AbstractUser):
    """
    Custom User model for CarePAL system
    Supports multiple user types: Patients, Family Members, Doctors, Admins
    """
    
    USER_TYPE_CHOICES = [
        ('PATIENT', 'Patient'),
        ('FAMILY', 'Family Member'),
        ('DOCTOR', 'Doctor'),
        ('ADMIN', 'Admin'),
    ]
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='PATIENT')
    phone_number = models.CharField(validators=[phone_regex], max_length=17, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.user_type})"
    
    @property
    def age(self):
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None


class ClinicalRelationship(models.Model):
    """
    Links a DOCTOR user to the PatientProfiles they are authorised to view/manage.
    """
    ROLE_CHOICES = [
        ('PRIMARY', 'Primary Physician'),
        ('SPECIALIST', 'Specialist'),
        ('NURSE', 'Nurse / Paramedic'),
        ('CONSULTANT', 'Consultant'),
    ]

    doctor = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='clinical_relationships',
        limit_choices_to={'user_type': 'DOCTOR'},
    )
    patient = models.ForeignKey(
        'patients.PatientProfile',
        on_delete=models.CASCADE,
        related_name='clinical_relationships',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='PRIMARY')

    # Granular permissions — add new ones here as features expand
    can_view_vitals = models.BooleanField(default=True)
    can_view_activity_log = models.BooleanField(default=True)
    can_view_medications = models.BooleanField(default=True)
    can_edit_medications = models.BooleanField(default=True)
    can_view_alerts = models.BooleanField(default=True)
    can_view_appointments = models.BooleanField(default=True)
    can_edit_appointments = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clinical_relationships'
        unique_together = ['doctor', 'patient']

    def __str__(self):
        return f"Dr {self.doctor.get_full_name()} → {self.patient.user.get_full_name()}"

    def has_permission(self, permission):
        permission_map = {
            'view_vitals': self.can_view_vitals,
            'view_activity_log': self.can_view_activity_log,
            'view_medications': self.can_view_medications,
            'edit_medications': self.can_edit_medications,
            'view_alerts': self.can_view_alerts,
            'view_appointments': self.can_view_appointments,
            'edit_appointments': self.can_edit_appointments,
        }
        return permission_map.get(permission, False)
