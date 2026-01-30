from django.db import models
from django.contrib.auth import get_user_model
from patients.models import PatientProfile
import uuid

User = get_user_model()

class ABHAProfile(models.Model):
    """Store ABHA credentials for patients"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.OneToOneField(PatientProfile, on_delete=models.CASCADE, related_name='abha_profile')
    
    # ABHA Identifiers
    abha_address = models.CharField(max_length=50, unique=True, db_index=True)
    abha_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    # Demographics (synced from ABDM)
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20)
    mobile = models.CharField(max_length=15)
    email = models.EmailField(null=True, blank=True)
    
    # Session Management
    abdm_access_token = models.TextField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    refresh_token = models.TextField(null=True, blank=True)
    
    # Consent Preferences
    auto_approve_carepal = models.BooleanField(default=True)  # Auto-approve CarePAL's own data requests
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'abdm_abha_profiles'
        verbose_name = 'ABHA Profile'
        verbose_name_plural = 'ABHA Profiles'
    
    def __str__(self):
        return f"{self.abha_address} - {self.full_name}"
    
    @property
    def is_token_valid(self):
        if not self.token_expires_at:
            return False
        from django.utils import timezone
        return timezone.now() < self.token_expires_at


class CareContext(models.Model):
    """Represents a logical grouping of health records"""
    
    CONTEXT_TYPES = [
        ('vitals', 'Vital Signs Monitoring'),
        ('medications', 'Medication Records'),
        ('ai_consultations', 'AI Assistant Consultations'),
        ('emergency', 'Emergency Incidents'),
        ('lab_reports', 'Lab Reports'),
        ('external', 'External Provider Records'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='care_contexts')
    abha_profile = models.ForeignKey(ABHAProfile, on_delete=models.CASCADE, related_name='care_contexts')
    
    # Care Context Details
    context_type = models.CharField(max_length=50, choices=CONTEXT_TYPES)
    context_id = models.CharField(max_length=100, unique=True, db_index=True)  # e.g., "vitals-uuid"
    display_name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    
    # Linking Status
    is_linked = models.BooleanField(default=False)
    linked_at = models.DateTimeField(null=True, blank=True)
    link_reference_number = models.CharField(max_length=100, null=True, blank=True)
    
    # External Provider Info (if context is from external HIP)
    external_hip_id = models.CharField(max_length=100, null=True, blank=True)
    external_hip_name = models.CharField(max_length=200, null=True, blank=True)
    
    # Date Range
    from_date = models.DateField()
    to_date = models.DateField()
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'abdm_care_contexts'
        verbose_name = 'Care Context'
        verbose_name_plural = 'Care Contexts'
        indexes = [
            models.Index(fields=['patient', 'context_type']),
            models.Index(fields=['context_id']),
        ]
    
    def __str__(self):
        return f"{self.display_name} - {self.patient.user.get_full_name()}"


class ConsentRequest(models.Model):
    """Track consent requests for data sharing"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('granted', 'Granted'),
        ('denied', 'Denied'),
        ('revoked', 'Revoked'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    abha_profile = models.ForeignKey(ABHAProfile, on_delete=models.CASCADE, related_name='consent_requests')
    
    # Consent Identifiers
    consent_id = models.CharField(max_length=100, unique=True, db_index=True)
    consent_request_id = models.CharField(max_length=100, unique=True)
    
    # Requester Details
    requester_name = models.CharField(max_length=200)  # HIU name
    requester_id = models.CharField(max_length=100)  # HIU ID
    purpose = models.TextField()
    
    # Care Contexts Requested
    care_contexts = models.ManyToManyField(CareContext, related_name='consent_requests')
    
    # Time Bounds
    from_date = models.DateField()
    to_date = models.DateField()
    expires_at = models.DateTimeField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    granted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'abdm_consent_requests'
        verbose_name = 'Consent Request'
        verbose_name_plural = 'Consent Requests'
    
    def __str__(self):
        return f"Consent {self.consent_id} - {self.status}"


class HealthRecordTransfer(models.Model):
    """Log all health record transfers"""
    
    TRANSFER_TYPES = [
        ('push', 'Push to External HIU'),
        ('pull', 'Pull from External HIP'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consent_request = models.ForeignKey(ConsentRequest, on_delete=models.CASCADE, related_name='transfers')
    
    transfer_type = models.CharField(max_length=10, choices=TRANSFER_TYPES)
    care_context = models.ForeignKey(CareContext, on_delete=models.CASCADE)
    
    # Transfer Details
    transaction_id = models.CharField(max_length=100, unique=True)
    data_size_bytes = models.IntegerField(default=0)
    fhir_format = models.BooleanField(default=True)
    
    # Success/Failure
    is_successful = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    
    transferred_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'abdm_health_record_transfers'
        verbose_name = 'Health Record Transfer'
        verbose_name_plural = 'Health Record Transfers'
    
    def __str__(self):
        return f"{self.transfer_type} - {self.transaction_id}"


class ABDMSession(models.Model):
    """Temporary OTP sessions for linking/authentication"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Session Details
    txn_id = models.CharField(max_length=100, unique=True, db_index=True)
    mobile = models.CharField(max_length=15)
    otp = models.CharField(max_length=10)
    otp_hash = models.CharField(max_length=256)  # Hashed OTP for verification
    
    # Session Type
    session_type = models.CharField(max_length=50)  # 'registration', 'login', 'linking'
    
    # Related Objects
    abha_profile = models.ForeignKey(ABHAProfile, on_delete=models.CASCADE, null=True, blank=True)
    care_context = models.ForeignKey(CareContext, on_delete=models.CASCADE, null=True, blank=True)
    
    # Expiry
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'abdm_sessions'
        verbose_name = 'ABDM Session'
        verbose_name_plural = 'ABDM Sessions'
    
    def __str__(self):
        return f"{self.session_type} - {self.txn_id}"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

class ABDMSubscription(models.Model):
    """
    Represents a subscription for health data (HIU/PHR Lockers).
    Stores details about what data is being observed.
    """
    id = models.CharField(max_length=100, primary_key=True) # subscription_id
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    abha_address = models.CharField(max_length=50)
    
    # Status
    status = models.CharField(max_length=20, default='REQUESTED')
    
    # Subscription Details
    categories = models.JSONField(default=list) # List of health info types
    period_from = models.DateTimeField(null=True, blank=True)
    period_to = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'abdm_subscriptions'
        verbose_name = 'ABDM Subscription'
        verbose_name_plural = 'ABDM Subscriptions'
    
    def __str__(self):
        return f"{self.id} - {self.status}"
