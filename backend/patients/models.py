from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User

class PatientProfile(models.Model):
    """
    Extended profile for Patient users
    Contains medical and personal information specific to patients
    """
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
        ('bn', 'Bengali'),
        ('mr', 'Marathi'),
        ('gu', 'Gujarati'),
        ('kn', 'Kannada'),
        ('ml', 'Malayalam'),
    ]
    
    # One-to-One relationship with User
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    
    # Eka.Care Patient Directory Integration
    eka_patient_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="Eka.Care patient_id (also called oid)"
    )
    eka_patient_created = models.BooleanField(
        default=False,
        help_text="Whether patient exists in Eka.Care directory"
    )
    eka_patient_created_at = models.DateTimeField(null=True, blank=True)
    
    # ABHA Integration (optional but recommended)
    abha_number = models.CharField(
        max_length=14,
        unique=True,
        null=True,
        blank=True,
        help_text="14-digit ABHA number (e.g., 12-3456-7890-1234)"
    )
    abha_address = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ABHA address (e.g., patient@abdm)"
    )
    is_abha_verified = models.BooleanField(default=False)
    abha_created_at = models.DateTimeField(null=True, blank=True)
    
    # Sync metadata
    eka_sync_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Store sync status and additional Eka.Care data"
    )
    
    # Basic Information
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, null=True, blank=True)
    height_cm = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(50), MaxValueValidator(300)],
        null=True, 
        blank=True,
        help_text="Height in centimeters"
    )
    weight_kg = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(10), MaxValueValidator(500)],
        null=True, 
        blank=True,
        help_text="Weight in kilograms"
    )
    
    # Location
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')
    
    # Preferences
    preferred_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='en')
    
    # Health Information (stored as JSON)
    health_conditions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of chronic conditions: ['Diabetes', 'Hypertension', 'COPD']"
    )
    allergies = models.JSONField(
        default=list,
        blank=True,
        help_text="List of known allergies"
    )
    current_medications = models.JSONField(
        default=list,
        blank=True,
        help_text="List of current medications"
    )
    
    # Medical History
    medical_notes = models.TextField(blank=True, help_text="Additional medical history or notes")
    last_hospital_visit = models.DateField(null=True, blank=True)
    
    # System fields
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'patient_profiles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Patient Profile: {self.user.get_full_name()} (Eka: {self.eka_patient_id})"

    @property
    def partner_patient_id(self):
        """Partner patient ID sent to Eka.Care (our CarePAL ID)"""
        return f"carepal_{self.id}"
    
    @property
    def has_eka_patient(self):
        """Check if patient exists in Eka.Care directory"""
        return bool(self.eka_patient_id)
    
    @property
    def has_abha(self):
        """Check if patient has ABHA"""
        return bool(self.abha_number)
    
    @property
    def bmi(self):
        """Calculate BMI if height and weight are available"""
        if self.height_cm and self.weight_kg:
            height_m = float(self.height_cm) / 100
            bmi = float(self.weight_kg) / (height_m ** 2)
            return round(bmi, 2)
        return None
    
    @property
    def bmi_category(self):
        """Return BMI category"""
        bmi = self.bmi
        if not bmi:
            return None
        if bmi < 18.5:
            return "Underweight"
        elif 18.5 <= bmi < 25:
            return "Normal"
        elif 25 <= bmi < 30:
            return "Overweight"
        else:
            return "Obese"
    
    @property
    def full_address(self):
        """Return formatted full address"""
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.pincode,
            self.country
        ]
        return ", ".join([p for p in parts if p])


class EmergencyContact(models.Model):
    """
    Emergency contacts for patients
    Multiple contacts can be added per patient
    """
    
    RELATIONSHIP_CHOICES = [
        ('SPOUSE', 'Spouse'),
        ('PARENT', 'Parent'),
        ('CHILD', 'Child'),
        ('SIBLING', 'Sibling'),
        ('FRIEND', 'Friend'),
        ('CAREGIVER', 'Caregiver'),
        ('DOCTOR', 'Doctor'),
        ('OTHER', 'Other'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile, 
        on_delete=models.CASCADE, 
        related_name='emergency_contacts'
    )
    
    # Contact Information
    name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    phone_number = models.CharField(max_length=17)
    alternate_phone = models.CharField(max_length=17, blank=True)
    email = models.EmailField(blank=True)
    
    # Priority
    is_primary = models.BooleanField(default=False, help_text="Primary emergency contact")
    priority_order = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Order in which to contact (1 = first)"
    )
    
    # Additional Info
    notes = models.TextField(blank=True, help_text="Additional information about this contact")
    
    # System fields
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'emergency_contacts'
        ordering = ['priority_order']
        unique_together = ['patient', 'phone_number']
    
    def __str__(self):
        return f"{self.name} ({self.relationship}) - {self.patient.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        # If this is set as primary, unset other primary contacts
        if self.is_primary:
            EmergencyContact.objects.filter(
                patient=self.patient, 
                is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)


class HealthCondition(models.Model):
    """
    Predefined health conditions catalog
    Used for standardizing health condition names
    """
    
    CATEGORY_CHOICES = [
        ('CARDIOVASCULAR', 'Cardiovascular'),
        ('RESPIRATORY', 'Respiratory'),
        ('ENDOCRINE', 'Endocrine'),
        ('NEUROLOGICAL', 'Neurological'),
        ('MUSCULOSKELETAL', 'Musculoskeletal'),
        ('RENAL', 'Renal'),
        ('DIGESTIVE', 'Digestive'),
        ('MENTAL', 'Mental Health'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    common_symptoms = models.JSONField(default=list, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'health_conditions'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.category})"
