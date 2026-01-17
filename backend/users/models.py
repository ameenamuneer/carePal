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
