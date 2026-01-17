from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from patients.models import PatientProfile
from users.models import User
from vitals.models import VitalReading
from medications.models import MedicationAdherence
from devices.models import DataSource
import json


class AlertType(models.Model):
    """
    Catalog of alert types supported by the system
    """
    
    CATEGORY_CHOICES = [
        ('VITAL_ANOMALY', 'Vital Sign Anomaly'),
        ('MEDICATION', 'Medication Related'),
        ('DEVICE', 'Device Issue'),
        ('HEALTH_TREND', 'Health Trend'),
        ('EMERGENCY', 'Emergency'),
        ('SYSTEM', 'System Notification'),
    ]
    
    SEVERITY_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    default_severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    
    # Template for alert message
    message_template = models.TextField(
        help_text="Message template with placeholders: {patient_name}, {value}, etc."
    )
    
    # Default delivery channels
    default_channels = models.JSONField(
        default=list,
        help_text="Default delivery channels: ['in_app', 'push', 'sms', 'email', 'voice_call']"
    )
    
    # Auto-escalation settings
    requires_acknowledgment = models.BooleanField(default=False)
    auto_escalate_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Auto-escalate if not acknowledged within X minutes"
    )
    
    # Grouping settings
    allow_grouping = models.BooleanField(
        default=True,
        help_text="Allow multiple similar alerts to be grouped"
    )
    grouping_window_minutes = models.IntegerField(
        default=30,
        help_text="Time window for grouping similar alerts"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'alert_types'
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Alert(models.Model):
    """
    Main alert/notification model
    """
    
    SEVERITY_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
        ('EMERGENCY', 'Emergency'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
        ('ESCALATED', 'Escalated'),
        ('EXPIRED', 'Expired'),
        ('FAILED', 'Failed'),
    ]
    
    alert_type = models.ForeignKey(
        AlertType,
        on_delete=models.PROTECT,
        related_name='alerts'
    )
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    
    # Alert details
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects (polymorphic relationships)
    vital_reading = models.ForeignKey(
        VitalReading,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts'
    )
    medication_adherence = models.ForeignKey(
        MedicationAdherence,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts'
    )
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts'
    )
    
    # Additional context
    context_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context: vital values, medication names, etc."
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Alert expires and becomes irrelevant after this time"
    )
    
    # Acknowledgment
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledgment_notes = models.TextField(blank=True)
    
    # Resolution
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts'
    )
    resolution_notes = models.TextField(blank=True)
    
    # Escalation
    is_escalated = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_level = models.IntegerField(default=0)
    
    # Grouping
    parent_alert = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grouped_alerts'
    )
    is_grouped = models.BooleanField(default=False)
    grouped_count = models.IntegerField(default=1)
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata: retry count, error messages, etc."
    )
    
    class Meta:
        db_table = 'alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'status', '-created_at']),
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['alert_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.alert_type.name} - {self.patient.user.get_full_name()} - {self.severity}"
    
    @property
    def is_expired(self):
        """Check if alert has expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def needs_escalation(self):
        """Check if alert needs escalation"""
        if self.status in ['ACKNOWLEDGED', 'RESOLVED', 'EXPIRED']:
            return False
        
        if not self.alert_type.requires_acknowledgment:
            return False
        
        if not self.alert_type.auto_escalate_minutes:
            return False
        
        time_since_creation = timezone.now() - self.created_at
        return time_since_creation.total_seconds() > (self.alert_type.auto_escalate_minutes * 60)


class AlertDelivery(models.Model):
    """
    Track delivery of alerts through different channels
    """
    
    CHANNEL_CHOICES = [
        ('IN_APP', 'In-App Notification'),
        ('PUSH', 'Push Notification'),
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('VOICE_CALL', 'Voice Call'),
        ('WHATSAPP', 'WhatsApp'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('BOUNCED', 'Bounced'),
    ]
    
    alert = models.ForeignKey(
        Alert,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='alert_deliveries'
    )
    
    # Delivery details
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    recipient_address = models.CharField(
        max_length=200,
        help_text="Phone number, email, device token, etc."
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    
    # External tracking
    external_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="External provider's message ID"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific metadata"
    )
    
    class Meta:
        db_table = 'alert_deliveries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['alert', 'channel']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.alert.title} → {self.recipient.get_full_name()} via {self.channel}"


class AlertRule(models.Model):
    """
    Custom alert rules for specific conditions
    """
    
    RULE_TYPE_CHOICES = [
        ('VITAL_THRESHOLD', 'Vital Threshold'),
        ('VITAL_TREND', 'Vital Trend'),
        ('MEDICATION_ADHERENCE', 'Medication Adherence'),
        ('DEVICE_STATUS', 'Device Status'),
        ('TIME_BASED', 'Time-Based'),
        ('CUSTOM', 'Custom Condition'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='alert_rules'
    )
    alert_type = models.ForeignKey(
        AlertType,
        on_delete=models.PROTECT,
        related_name='rules'
    )
    
    # Rule details
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    rule_type = models.CharField(max_length=30, choices=RULE_TYPE_CHOICES)
    
    # Conditions (stored as JSON)
    conditions = models.JSONField(
        default=dict,
        help_text="Rule conditions: {'vital_type': 'BP', 'operator': '>', 'threshold': 140}"
    )
    
    # Alert configuration
    override_severity = models.CharField(
        max_length=20,
        choices=Alert.SEVERITY_CHOICES,
        null=True,
        blank=True,
        help_text="Override default severity"
    )
    custom_message = models.TextField(
        blank=True,
        help_text="Custom message template"
    )
    
    # Delivery preferences
    delivery_channels = models.JSONField(
        default=list,
        blank=True,
        help_text="Specific channels for this rule"
    )
    
    # Recipients
    notify_patient = models.BooleanField(default=True)
    notify_family = models.BooleanField(default=True)
    notify_doctor = models.BooleanField(default=False)
    additional_recipients = models.JSONField(
        default=list,
        blank=True,
        help_text="List of user IDs to notify"
    )
    
    # Schedule
    active_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Only trigger during these hours"
    )
    active_hours_end = models.TimeField(null=True, blank=True)
    active_days = models.JSONField(
        default=list,
        blank=True,
        help_text="[0-6] where 0=Monday. Empty = all days"
    )
    
    # Rate limiting
    max_alerts_per_hour = models.IntegerField(
        default=10,
        help_text="Maximum alerts this rule can generate per hour"
    )
    cooldown_minutes = models.IntegerField(
        default=0,
        help_text="Minimum minutes between alerts from this rule"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_alert_rules'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'alert_rules'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.patient.user.get_full_name()}"
    
    def can_trigger(self):
        """Check if rule can trigger based on rate limits and schedule"""
        if not self.is_active:
            return False
        
        # Check active hours
        if self.active_hours_start and self.active_hours_end:
            now_time = timezone.now().time()
            if not (self.active_hours_start <= now_time <= self.active_hours_end):
                return False
        
        # Check active days
        if self.active_days:
            today = timezone.now().weekday()
            if today not in self.active_days:
                return False
        
        # Check cooldown
        if self.cooldown_minutes and self.last_triggered_at:
            time_since_last = timezone.now() - self.last_triggered_at
            if time_since_last.total_seconds() < (self.cooldown_minutes * 60):
                return False
        
        # Check hourly rate limit
        if self.max_alerts_per_hour:
            one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
            recent_alerts = Alert.objects.filter(
                patient=self.patient,
                alert_type=self.alert_type,
                created_at__gte=one_hour_ago
            ).count()
            
            if recent_alerts >= self.max_alerts_per_hour:
                return False
        
        return True


class NotificationPreference(models.Model):
    """
    User preferences for receiving alerts
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Channel preferences
    enable_in_app = models.BooleanField(default=True)
    enable_push = models.BooleanField(default=True)
    enable_sms = models.BooleanField(default=True)
    enable_email = models.BooleanField(default=True)
    enable_voice_call = models.BooleanField(default=False)
    
    # Severity filters (which severities to receive)
    receive_info = models.BooleanField(default=True)
    receive_warning = models.BooleanField(default=True)
    receive_critical = models.BooleanField(default=True)
    receive_emergency = models.BooleanField(default=True)
    
    # Category filters
    category_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Category-specific preferences: {'VITAL_ANOMALY': True, 'MEDICATION': True}"
    )
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    quiet_hours_exceptions = models.JSONField(
        default=list,
        blank=True,
        help_text="Severity levels that override quiet hours: ['CRITICAL', 'EMERGENCY']"
    )
    
    # Contact information
    sms_phone_number = models.CharField(max_length=20, blank=True)
    voice_call_number = models.CharField(max_length=20, blank=True)
    email_address = models.EmailField(blank=True)
    push_device_tokens = models.JSONField(
        default=list,
        blank=True,
        help_text="List of device tokens for push notifications"
    )
    
    # Digest settings
    enable_daily_digest = models.BooleanField(default=False)
    digest_time = models.TimeField(null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
    
    def __str__(self):
        return f"Notification preferences for {self.user.get_full_name()}"
    
    def is_in_quiet_hours(self, severity=None):
        """Check if currently in quiet hours"""
        if not self.quiet_hours_enabled:
            return False
        
        # Check if severity overrides quiet hours
        if severity and self.quiet_hours_exceptions:
            if severity in self.quiet_hours_exceptions:
                return False
        
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        now_time = timezone.now().time()
        return self.quiet_hours_start <= now_time <= self.quiet_hours_end


class AlertEscalation(models.Model):
    """
    Track alert escalations
    """
    
    ESCALATION_TYPE_CHOICES = [
        ('AUTO', 'Automatic'),
        ('MANUAL', 'Manual'),
        ('SEVERITY_UPGRADE', 'Severity Upgrade'),
    ]
    
    alert = models.ForeignKey(
        Alert,
        on_delete=models.CASCADE,
        related_name='escalations'
    )
    
    escalation_type = models.CharField(max_length=20, choices=ESCALATION_TYPE_CHOICES)
    escalation_level = models.IntegerField()
    
    # What triggered escalation
    trigger_reason = models.TextField()
    
    # Actions taken
    previous_severity = models.CharField(max_length=20, blank=True)
    new_severity = models.CharField(max_length=20, blank=True)
    
    additional_recipients = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional users notified during escalation"
    )
    additional_channels = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional channels used during escalation"
    )
    
    escalated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    escalated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'alert_escalations'
        ordering = ['-escalated_at']
    
    def __str__(self):
        return f"Escalation Level {self.escalation_level} - {self.alert.title}"


class AlertTemplate(models.Model):
    """
    Reusable alert message templates
    """
    
    name = models.CharField(max_length=200)
    alert_type = models.ForeignKey(
        AlertType,
        on_delete=models.CASCADE,
        related_name='templates'
    )
    
    # Template content
    subject_template = models.CharField(max_length=200)
    message_template = models.TextField()
    
    # Available for different channels
    supports_sms = models.BooleanField(default=True)
    supports_email = models.BooleanField(default=True)
    supports_push = models.BooleanField(default=True)
    supports_voice = models.BooleanField(default=False)
    
    # Voice-specific
    voice_script = models.TextField(
        blank=True,
        help_text="Script for voice call notifications"
    )
    
    # Localization
    language = models.CharField(max_length=10, default='en')
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'alert_templates'
        ordering = ['alert_type', 'language']
    
    def __str__(self):
        return f"{self.name} ({self.language})"
    
    def render(self, context):
        """Render template with context data"""
        subject = self.subject_template.format(**context)
        message = self.message_template.format(**context)
        return subject, message


class AlertStatistics(models.Model):
    """
    Aggregated alert statistics for analytics
    Computed periodically by background tasks
    """
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='alert_statistics'
    )
    
    # Time period
    period_start = models.DateField()
    period_end = models.DateField()
    period_label = models.CharField(max_length=50)  # 'daily', 'weekly', 'monthly'
    
    # Alert counts by severity
    total_alerts = models.IntegerField(default=0)
    info_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)
    critical_count = models.IntegerField(default=0)
    emergency_count = models.IntegerField(default=0)
    
    # Alert counts by category
    vital_anomaly_count = models.IntegerField(default=0)
    medication_count = models.IntegerField(default=0)
    device_count = models.IntegerField(default=0)
    health_trend_count = models.IntegerField(default=0)
    
    # Response metrics
    avg_acknowledgment_time_minutes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    avg_resolution_time_minutes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    escalation_count = models.IntegerField(default=0)
    unacknowledged_count = models.IntegerField(default=0)
    
    # Insights
    insights = models.JSONField(default=list, blank=True)
    
    computed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'alert_statistics'
        ordering = ['-period_end']
        unique_together = ['patient', 'period_label', 'period_start']
    
    def __str__(self):
        return f"Alert stats for {self.patient.user.get_full_name()} - {self.period_label}"
