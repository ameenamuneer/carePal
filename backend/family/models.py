from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User
from patients.models import PatientProfile
import secrets


class FamilyMember(models.Model):
    """
    Link between family members and patients they can monitor
    """
    
    RELATIONSHIP_CHOICES = [
        ('SPOUSE', 'Spouse'),
        ('CHILD', 'Child'),
        ('PARENT', 'Parent'),
        ('SIBLING', 'Sibling'),
        ('GRANDCHILD', 'Grandchild'),
        ('GRANDPARENT', 'Grandparent'),
        ('OTHER_RELATIVE', 'Other Relative'),
        ('FRIEND', 'Friend'),
        ('CAREGIVER', 'Professional Caregiver'),
        ('GUARDIAN', 'Legal Guardian'),
    ]
    
    ACCESS_LEVEL_CHOICES = [
        ('VIEW_ONLY', 'View Only'),
        ('BASIC', 'Basic Access'),
        ('FULL', 'Full Access'),
        ('ADMIN', 'Admin Access'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='family_memberships'
    )
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='family_members'
    )
    
    # Relationship details
    relationship = models.CharField(max_length=30, choices=RELATIONSHIP_CHOICES)
    relationship_details = models.TextField(
        blank=True,
        help_text="Additional details about the relationship"
    )
    
    # Access control
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='BASIC')
    
    # Permissions — add new ones here as features expand
    can_view_vitals = models.BooleanField(default=True)
    can_view_medications = models.BooleanField(default=True)
    can_view_activity_log = models.BooleanField(default=True)
    can_view_alerts = models.BooleanField(default=True)
    can_view_medical_history = models.BooleanField(default=False)
    can_acknowledge_alerts = models.BooleanField(default=True)
    can_add_notes = models.BooleanField(default=True)
    can_manage_medications = models.BooleanField(default=False)
    can_invite_others = models.BooleanField(default=False)
    
    # Status
    is_primary_caregiver = models.BooleanField(
        default=False,
        help_text="Primary point of contact for this patient"
    )
    is_emergency_contact = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Invitation tracking
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_family_invitations'
    )
    invitation_accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Activity tracking
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    view_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'family_members'
        ordering = ['-is_primary_caregiver', 'relationship']
        unique_together = ['user', 'patient']
        indexes = [
            models.Index(fields=['patient', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_relationship_display()} of {self.patient.user.get_full_name()}"
    
    def has_permission(self, permission):
        """Check if family member has specific permission"""
        permission_map = {
            'view_vitals': self.can_view_vitals,
            'view_medications': self.can_view_medications,
            'view_activity_log': self.can_view_activity_log,
            'view_alerts': self.can_view_alerts,
            'view_medical_history': self.can_view_medical_history,
            'acknowledge_alerts': self.can_acknowledge_alerts,
            'add_notes': self.can_add_notes,
            'manage_medications': self.can_manage_medications,
            'invite_others': self.can_invite_others,
        }
        return permission_map.get(permission, False)
    
    def record_view(self):
        """Record that family member viewed patient data"""
        self.last_viewed_at = timezone.now()
        self.view_count += 1
        self.save(update_fields=['last_viewed_at', 'view_count'])


class FamilyInvitation(models.Model):
    """
    Invitations sent to family members to join patient monitoring
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='family_invitations'
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='family_invitations_sent'
    )
    
    # Invitee information
    invitee_email = models.EmailField()
    invitee_phone = models.CharField(max_length=20, blank=True)
    invitee_name = models.CharField(max_length=200, blank=True)
    
    # Invitation details
    relationship = models.CharField(max_length=30, choices=FamilyMember.RELATIONSHIP_CHOICES)
    access_level = models.CharField(
        max_length=20,
        choices=FamilyMember.ACCESS_LEVEL_CHOICES,
        default='BASIC'
    )
    personal_message = models.TextField(blank=True)
    
    # Invitation token
    invitation_token = models.CharField(max_length=100, unique=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    
    # Accepted user (if they register)
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='family_invitations_accepted'
    )
    
    class Meta:
        db_table = 'family_invitations'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invitation to {self.invitee_email} for {self.patient.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.invitation_token:
            self.invitation_token = secrets.token_urlsafe(32)
        if not self.expires_at:
            # Default: expires in 7 days
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status == 'PENDING'


class FamilyNote(models.Model):
    """
    Notes added by family members about patient
    """
    
    NOTE_TYPE_CHOICES = [
        ('OBSERVATION', 'General Observation'),
        ('CONCERN', 'Concern'),
        ('MEDICATION', 'Medication Related'),
        ('APPOINTMENT', 'Appointment Related'),
        ('SYMPTOM', 'Symptom Report'),
        ('BEHAVIOR', 'Behavior Change'),
        ('OTHER', 'Other'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='family_notes'
    )
    family_member = models.ForeignKey(
        FamilyMember,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    
    # Note details
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Related objects
    related_vital_reading = models.ForeignKey(
        'vitals.VitalReading',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='family_notes'
    )
    related_medication = models.ForeignKey(
        'medications.Medication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='family_notes'
    )
    related_alert = models.ForeignKey(
        'alerts.Alert',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='family_notes'
    )
    
    # Privacy
    is_private = models.BooleanField(
        default=False,
        help_text="Visible only to creator and primary caregiver"
    )
    is_important = models.BooleanField(default=False)
    
    # Attachments
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="List of attachment URLs/IDs"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'family_notes'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note by {self.family_member.user.get_full_name()} - {self.title}"


class FamilyActivityLog(models.Model):
    """
    Log of family member activities for audit trail
    """
    
    ACTION_CHOICES = [
        ('VIEWED_DASHBOARD', 'Viewed Dashboard'),
        ('VIEWED_VITALS', 'Viewed Vitals'),
        ('VIEWED_MEDICATIONS', 'Viewed Medications'),
        ('VIEWED_ALERTS', 'Viewed Alerts'),
        ('ACKNOWLEDGED_ALERT', 'Acknowledged Alert'),
        ('ADDED_NOTE', 'Added Note'),
        ('UPDATED_MEDICATION', 'Updated Medication'),
        ('INVITED_MEMBER', 'Invited Family Member'),
        ('UPDATED_PERMISSIONS', 'Updated Permissions'),
        ('DOWNLOADED_REPORT', 'Downloaded Report'),
    ]
    
    family_member = models.ForeignKey(
        FamilyMember,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='family_activity_logs'
    )
    
    # Activity details
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    
    # Related objects (polymorphic)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context data"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'family_activity_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['family_member', '-created_at']),
            models.Index(fields=['patient', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.family_member.user.get_full_name()} - {self.get_action_display()}"


class FamilyCommunication(models.Model):
    """
    Communication/messages between family members
    """
    
    MESSAGE_TYPE_CHOICES = [
        ('GENERAL', 'General Message'),
        ('ALERT_DISCUSSION', 'Alert Discussion'),
        ('CARE_COORDINATION', 'Care Coordination'),
        ('QUESTION', 'Question'),
        ('UPDATE', 'Status Update'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='family_communications'
    )
    sender = models.ForeignKey(
        FamilyMember,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    
    # Message details
    message_type = models.CharField(max_length=30, choices=MESSAGE_TYPE_CHOICES, default='GENERAL')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects
    related_alert = models.ForeignKey(
        'alerts.Alert',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='family_communications'
    )
    related_note = models.ForeignKey(
        FamilyNote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='communications'
    )
    
    # Thread support
    parent_message = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    # Read tracking
    read_by = models.JSONField(
        default=list,
        blank=True,
        help_text="List of family member IDs who read this"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'family_communications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message from {self.sender.user.get_full_name()} - {self.subject}"
    
    def mark_as_read(self, family_member_id):
        """Mark message as read by family member"""
        if family_member_id not in self.read_by:
            self.read_by.append(family_member_id)
            self.save(update_fields=['read_by'])


class CareSchedule(models.Model):
    """
    Shared care schedule among family members
    """
    
    SCHEDULE_TYPE_CHOICES = [
        ('VISIT', 'In-Person Visit'),
        ('CALL', 'Phone Call Check-in'),
        ('MEDICATION_HELP', 'Medication Assistance'),
        ('APPOINTMENT', 'Medical Appointment'),
        ('ACTIVITY', 'Activity/Exercise'),
        ('MEAL', 'Meal Preparation'),
        ('OTHER', 'Other Care Task'),
    ]
    
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('MISSED', 'Missed'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='care_schedules'
    )
    assigned_to = models.ForeignKey(
        FamilyMember,
        on_delete=models.CASCADE,
        related_name='assigned_care_tasks'
    )
    created_by = models.ForeignKey(
        FamilyMember,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_care_tasks'
    )
    
    # Schedule details
    schedule_type = models.CharField(max_length=30, choices=SCHEDULE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Timing
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    
    # Recurrence
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.JSONField(
        default=dict,
        blank=True,
        help_text="{'frequency': 'daily/weekly/monthly', 'interval': 1, 'end_date': 'YYYY-MM-DD'}"
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    
    # Reminders
    send_reminder = models.BooleanField(default=True)
    reminder_minutes_before = models.IntegerField(default=60)
    reminder_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'care_schedules'
        ordering = ['scheduled_date', 'scheduled_time']
    
    def __str__(self):
        return f"{self.title} - {self.scheduled_date}"
    
    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if self.status in ['COMPLETED', 'CANCELLED']:
            return False
        
        now = timezone.now()
        scheduled_datetime = timezone.make_aware(
            timezone.datetime.combine(self.scheduled_date, self.scheduled_time or timezone.datetime.min.time())
        )
        
        return now > scheduled_datetime


class FamilyDashboardSettings(models.Model):
    """
    Customizable dashboard settings per family member
    """
    
    family_member = models.OneToOneField(
        FamilyMember,
        on_delete=models.CASCADE,
        related_name='dashboard_settings'
    )
    
    # Widget preferences
    visible_widgets = models.JSONField(
        default=list,
        help_text="List of widget IDs to show: ['vitals_chart', 'medication_schedule', 'alerts', 'notes']"
    )
    widget_order = models.JSONField(
        default=list,
        help_text="Order of widgets on dashboard"
    )
    
    # Data preferences
    default_time_range = models.CharField(
        max_length=20,
        default='7days',
        help_text="Default time range for charts: '24hours', '7days', '30days', '90days'"
    )
    show_vital_trends = models.BooleanField(default=True)
    show_medication_adherence = models.BooleanField(default=True)
    show_alert_history = models.BooleanField(default=True)
    
    # Notification preferences (separate from user preferences)
    notify_on_critical_alerts = models.BooleanField(default=True)
    notify_on_missed_medications = models.BooleanField(default=True)
    notify_on_schedule_reminders = models.BooleanField(default=True)
    daily_summary_enabled = models.BooleanField(default=False)
    daily_summary_time = models.TimeField(null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'family_dashboard_settings'
    
    def __str__(self):
        return f"Dashboard settings for {self.family_member.user.get_full_name()}"
