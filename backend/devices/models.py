from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from cryptography.fernet import Fernet
from django.conf import settings
from patients.models import PatientProfile
from users.models import User
from vitals.models import DataSource
import json


class CloudProvider(models.Model):
    """
    Catalog of supported cloud health data providers
    """
    
    PROVIDER_CHOICES = [
        ('FITBIT', 'Fitbit'),
        ('GOOGLE_FIT', 'Google Fit'),
        ('APPLE_HEALTH', 'Apple Health'),
        ('SAMSUNG_HEALTH', 'Samsung Health'),
        ('WITHINGS', 'Withings'),
        ('GARMIN', 'Garmin Connect'),
        ('POLAR', 'Polar Flow'),
    ]
    
    name = models.CharField(max_length=50, choices=PROVIDER_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    
    # OAuth Configuration
    client_id = models.CharField(max_length=500, blank=True)
    client_secret = models.CharField(max_length=500, blank=True)
    authorization_url = models.URLField(max_length=500)
    token_url = models.URLField(max_length=500)
    api_base_url = models.URLField(max_length=500)
    scopes = models.JSONField(
        default=list,
        help_text="Required OAuth scopes"
    )
    
    # Configuration
    supports_webhooks = models.BooleanField(default=False)
    webhook_url = models.URLField(max_length=500, blank=True)
    rate_limit_per_hour = models.IntegerField(default=150)
    sync_interval_minutes = models.IntegerField(default=15)
    
    # Supported data types
    supported_vitals = models.JSONField(
        default=list,
        help_text="List of vital types this provider supports: ['heart_rate', 'steps', 'sleep']"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cloud_providers'
        ordering = ['display_name']
    
    def __str__(self):
        return self.display_name


class CloudAPICredential(models.Model):
    """
    Store OAuth credentials for cloud API integrations
    Tokens are encrypted at rest
    """
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('REVOKED', 'Revoked'),
        ('ERROR', 'Error'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='cloud_credentials'
    )
    provider = models.ForeignKey(
        CloudProvider,
        on_delete=models.PROTECT,
        related_name='credentials'
    )
    data_source = models.OneToOneField(
        DataSource,
        on_delete=models.CASCADE,
        related_name='cloud_credential',
        null=True,
        blank=True
    )
    
    # Encrypted tokens
    access_token_encrypted = models.TextField()
    refresh_token_encrypted = models.TextField(blank=True)
    
    # Token metadata
    token_type = models.CharField(max_length=50, default='Bearer')
    expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(blank=True)
    
    # User info from provider
    provider_user_id = models.CharField(max_length=200, blank=True)
    provider_user_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional user info from provider"
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    
    # Consent
    consent_given_at = models.DateTimeField(auto_now_add=True)
    consent_revoked_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cloud_api_credentials'
        ordering = ['-created_at']
        unique_together = ['patient', 'provider']
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.provider.display_name}"
    
    @staticmethod
    def _get_cipher():
        """Get encryption cipher"""
        # In production, store this key securely (environment variable, secrets manager)
        key = getattr(settings, 'ENCRYPTION_KEY', Fernet.generate_key())
        return Fernet(key)
    
    def set_access_token(self, token):
        """Encrypt and store access token"""
        cipher = self._get_cipher()
        self.access_token_encrypted = cipher.encrypt(token.encode()).decode()
    
    def get_access_token(self):
        """Decrypt and return access token"""
        if not self.access_token_encrypted:
            return None
        cipher = self._get_cipher()
        return cipher.decrypt(self.access_token_encrypted.encode()).decode()
    
    def set_refresh_token(self, token):
        """Encrypt and store refresh token"""
        if not token:
            return
        cipher = self._get_cipher()
        self.refresh_token_encrypted = cipher.encrypt(token.encode()).decode()
    
    def get_refresh_token(self):
        """Decrypt and return refresh token"""
        if not self.refresh_token_encrypted:
            return None
        cipher = self._get_cipher()
        return cipher.decrypt(self.refresh_token_encrypted.encode()).decode()
    
    @property
    def is_token_expired(self):
        """Check if access token is expired"""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at
    
    @property
    def needs_refresh(self):
        """Check if token needs refresh (expires in less than 1 hour)"""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at - timezone.timedelta(hours=1)


class DeviceSyncLog(models.Model):
    """
    Log all device synchronization attempts
    """
    
    STATUS_CHOICES = [
        ('STARTED', 'Started'),
        ('SUCCESS', 'Success'),
        ('PARTIAL', 'Partial Success'),
        ('FAILED', 'Failed'),
    ]
    
    SYNC_TYPE_CHOICES = [
        ('MANUAL', 'Manual'),
        ('SCHEDULED', 'Scheduled'),
        ('WEBHOOK', 'Webhook'),
        ('REAL_TIME', 'Real-time'),
    ]
    
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='sync_logs'
    )
    cloud_credential = models.ForeignKey(
        CloudAPICredential,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sync_logs'
    )
    
    # Sync details
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPE_CHOICES)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='STARTED')
    records_fetched = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    
    # Time range synced
    sync_from_date = models.DateTimeField(null=True, blank=True)
    sync_to_date = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional sync metadata: API calls made, rate limits, etc."
    )
    
    class Meta:
        db_table = 'device_sync_logs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['data_source', '-started_at']),
            models.Index(fields=['status', '-started_at']),
        ]
    
    def __str__(self):
        return f"Sync {self.id} - {self.data_source.device_name} - {self.status}"
    
    def complete(self, status, error_message=''):
        """Mark sync as complete"""
        self.completed_at = timezone.now()
        self.status = status
        self.error_message = error_message
        
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()
        
        self.save()


class DeviceCalibration(models.Model):
    """
    Track device calibration for accuracy
    """
    
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='calibrations'
    )
    
    calibrated_at = models.DateTimeField()
    calibrated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    
    # Calibration data
    calibration_type = models.CharField(
        max_length=50,
        help_text="'baseline', 'offset_adjustment', 'reference_comparison'"
    )
    calibration_values = models.JSONField(
        default=dict,
        help_text="Calibration parameters and adjustments"
    )
    
    # Reference measurement
    reference_device = models.CharField(max_length=200, blank=True)
    reference_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    device_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    deviation = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Difference between device and reference"
    )
    
    notes = models.TextField(blank=True)
    next_calibration_due = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'device_calibrations'
        ordering = ['-calibrated_at']
    
    def __str__(self):
        return f"Calibration for {self.data_source.device_name} on {self.calibrated_at.date()}"


class DataConflict(models.Model):
    """
    Track conflicts when multiple devices report different values
    """
    
    RESOLUTION_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('USE_PRIMARY', 'Use Primary Device'),
        ('USE_AVERAGE', 'Use Average'),
        ('USE_LATEST', 'Use Latest'),
        ('MANUAL', 'Manual Selection'),
        ('IGNORE', 'Ignore Conflict'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='data_conflicts'
    )
    vital_type = models.ForeignKey(
        'vitals.VitalType',
        on_delete=models.CASCADE
    )
    
    # Conflict details
    conflict_time = models.DateTimeField()
    time_window_minutes = models.IntegerField(
        default=5,
        help_text="Conflict if readings within this window differ significantly"
    )
    
    # Conflicting readings
    readings = models.JSONField(
        default=list,
        help_text="List of conflicting readings with source and value"
    )
    
    # Deviation
    max_deviation = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Maximum difference between readings"
    )
    deviation_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Resolution
    resolution_method = models.CharField(
        max_length=20,
        choices=RESOLUTION_CHOICES,
        default='PENDING'
    )
    selected_reading_id = models.IntegerField(null=True, blank=True)
    resolved_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'data_conflicts'
        ordering = ['-conflict_time']
    
    def __str__(self):
        return f"Conflict: {self.vital_type.name} at {self.conflict_time} ({self.max_deviation} difference)"


class WebhookSubscription(models.Model):
    """
    Track webhook subscriptions for real-time updates from providers
    """
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PENDING', 'Pending Verification'),
        ('FAILED', 'Failed'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    cloud_credential = models.ForeignKey(
        CloudAPICredential,
        on_delete=models.CASCADE,
        related_name='webhook_subscriptions'
    )
    
    # Subscription details
    subscription_id = models.CharField(max_length=200, unique=True)
    callback_url = models.URLField(max_length=500)
    
    # What to listen for
    event_types = models.JSONField(
        default=list,
        help_text="List of event types: ['activity', 'sleep', 'body']"
    )
    
    # Verification
    verification_code = models.CharField(max_length=200, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    last_notification_at = models.DateTimeField(null=True, blank=True)
    notification_count = models.IntegerField(default=0)
    
    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'webhook_subscriptions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Webhook: {self.cloud_credential.provider.display_name} - {self.subscription_id}"


class BluetoothDeviceSession(models.Model):
    """
    Track Bluetooth device connection sessions
    """
    
    STATUS_CHOICES = [
        ('CONNECTED', 'Connected'),
        ('DISCONNECTED', 'Disconnected'),
        ('TIMEOUT', 'Timeout'),
        ('ERROR', 'Error'),
    ]
    
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='bluetooth_sessions'
    )
    
    # Session info
    session_id = models.CharField(max_length=100, unique=True)
    connected_at = models.DateTimeField()
    disconnected_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Connection details
    signal_strength = models.IntegerField(
        null=True,
        blank=True,
        help_text="RSSI value"
    )
    battery_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Data transfer
    readings_received = models.IntegerField(default=0)
    bytes_transferred = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True)
    
    # Metadata
    device_firmware = models.CharField(max_length=50, blank=True)
    device_hardware = models.CharField(max_length=50, blank=True)
    app_version = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'bluetooth_device_sessions'
        ordering = ['-connected_at']
    
    def __str__(self):
        return f"{self.data_source.device_name} session {self.session_id}"


class DevicePriority(models.Model):
    """
    Define device priority when multiple devices measure same vital
    """
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='device_priorities'
    )
    vital_type = models.ForeignKey(
        'vitals.VitalType',
        on_delete=models.CASCADE
    )
    
    # Ordered list of data sources (highest to lowest priority)
    priority_order = models.JSONField(
        default=list,
        help_text="List of data_source IDs in priority order: [3, 1, 5]"
    )
    
    # Rules
    use_average_if_close = models.BooleanField(
        default=False,
        help_text="Average values if they're within threshold"
    )
    threshold_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.0,
        help_text="Consider values 'close' if within this percentage"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'device_priorities'
        unique_together = ['patient', 'vital_type']
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.vital_type.name} priority"
