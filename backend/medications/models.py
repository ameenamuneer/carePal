from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import datetime, timedelta
from patients.models import PatientProfile
from users.models import User


class Medication(models.Model):
    """
    Main medication prescription model
    Stores medication details and prescription information
    """
    
    FORM_CHOICES = [
        ('TABLET', 'Tablet'),
        ('CAPSULE', 'Capsule'),
        ('LIQUID', 'Liquid/Syrup'),
        ('INJECTION', 'Injection'),
        ('DROPS', 'Drops'),
        ('INHALER', 'Inhaler'),
        ('SPRAY', 'Spray'),
        ('PATCH', 'Patch'),
        ('CREAM', 'Cream/Ointment'),
        ('POWDER', 'Powder'),
        ('OTHER', 'Other'),
    ]
    
    ROUTE_CHOICES = [
        ('ORAL', 'Oral'),
        ('SUBLINGUAL', 'Sublingual'),
        ('TOPICAL', 'Topical'),
        ('INHALATION', 'Inhalation'),
        ('INJECTION_IV', 'Intravenous'),
        ('INJECTION_IM', 'Intramuscular'),
        ('INJECTION_SC', 'Subcutaneous'),
        ('RECTAL', 'Rectal'),
        ('OPHTHALMIC', 'Eye'),
        ('OTIC', 'Ear'),
        ('NASAL', 'Nasal'),
    ]
    
    FREQUENCY_CHOICES = [
        ('ONCE_DAILY', 'Once Daily'),
        ('TWICE_DAILY', 'Twice Daily (BID)'),
        ('THREE_TIMES_DAILY', 'Three Times Daily (TID)'),
        ('FOUR_TIMES_DAILY', 'Four Times Daily (QID)'),
        ('EVERY_4_HOURS', 'Every 4 Hours'),
        ('EVERY_6_HOURS', 'Every 6 Hours'),
        ('EVERY_8_HOURS', 'Every 8 Hours'),
        ('EVERY_12_HOURS', 'Every 12 Hours'),
        ('WEEKLY', 'Weekly'),
        ('TWICE_WEEKLY', 'Twice Weekly'),
        ('MONTHLY', 'Monthly'),
        ('AS_NEEDED', 'As Needed (PRN)'),
        ('CUSTOM', 'Custom Schedule'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('DISCONTINUED', 'Discontinued'),
        ('ON_HOLD', 'On Hold'),
    ]

    SOURCE_CHOICES = [
        ('MANUAL', 'Manual Entry'),
        ('EKA_CARE', 'Imported from Eka.Care'),
        ('HOSPITAL', 'Hospital System'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='medications'
    )
    
    # Medication Details
    medication_name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    brand_name = models.CharField(max_length=200, blank=True)

    # Source tracking
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='MANUAL'
    )
    
    # Eka.Care prescription metadata
    eka_prescription_id = models.CharField(max_length=100, null=True, blank=True)
    eka_drug_id = models.CharField(max_length=100, null=True, blank=True)
    eka_imported_at = models.DateTimeField(null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    # Dosage Information
    dosage = models.CharField(
        max_length=100,
        help_text="e.g., '500mg', '10ml', '2 puffs'"
    )
    form = models.CharField(max_length=20, choices=FORM_CHOICES)
    route = models.CharField(max_length=20, choices=ROUTE_CHOICES)
    
    # Schedule
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    times_per_day = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    
    # Duration
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    duration_days = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total duration in days"
    )
    
    # Instructions
    instructions = models.TextField(
        help_text="Special instructions: 'Take with food', 'Take on empty stomach', etc."
    )
    special_instructions = models.TextField(blank=True)
    
    # Prescription Info
    prescribed_by = models.CharField(max_length=200, blank=True)
    prescription_number = models.CharField(max_length=100, blank=True)
    prescribed_date = models.DateField(null=True, blank=True)
    
    # Inventory
    quantity_prescribed = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total quantity prescribed"
    )
    quantity_remaining = models.IntegerField(
        null=True,
        blank=True,
        help_text="Remaining quantity"
    )
    refills_allowed = models.IntegerField(default=0)
    refills_remaining = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    discontinuation_reason = models.TextField(blank=True)
    discontinued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discontinued_medications'
    )
    discontinued_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    side_effects = models.JSONField(
        default=list,
        blank=True,
        help_text="List of known side effects"
    )
    interactions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of drug interactions"
    )
    purpose = models.TextField(
        blank=True,
        help_text="What condition is this medication treating"
    )
    
    # System fields
    is_critical = models.BooleanField(
        default=False,
        help_text="Critical medication - missing doses require immediate alert"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_medications'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'medications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['status', 'start_date']),
        ]
    
    def __str__(self):
        return f"{self.medication_name} - {self.dosage} - {self.patient.user.get_full_name()}"
    
    @property
    def is_active(self):
        """Check if medication is currently active"""
        if self.status != 'ACTIVE':
            return False
        
        today = timezone.now().date()
        if self.start_date > today:
            return False
        
        if self.end_date and self.end_date < today:
            return False
        
        return True
    
    @property
    def needs_refill(self):
        """Check if medication needs refill"""
        if self.quantity_remaining is None:
            return False
        
        # Calculate days of supply remaining
        if self.times_per_day > 0:
            days_remaining = self.quantity_remaining / self.times_per_day
            return days_remaining <= 7  # Alert when 7 days or less remaining
        
        return False
    
    def save(self, *args, **kwargs):
        # Calculate end date from duration if not provided
        if not self.end_date and self.duration_days:
            self.end_date = self.start_date + timedelta(days=self.duration_days)
        
        # Initialize quantity remaining
        if self.quantity_remaining is None and self.quantity_prescribed:
            self.quantity_remaining = self.quantity_prescribed
        
        super().save(*args, **kwargs)


class MedicationSchedule(models.Model):
    """
    Detailed schedule for medication reminders
    Defines specific times when medication should be taken
    """
    
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    
    # Time of day
    time_of_day = models.TimeField()
    time_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="'Morning', 'Afternoon', 'Evening', 'Bedtime', etc."
    )
    
    # Days of week (for weekly medications)
    days_of_week = models.JSONField(
        default=list,
        blank=True,
        help_text="[0-6] where 0=Monday, 6=Sunday. Empty list = all days"
    )
    
    # Special conditions
    with_food = models.BooleanField(default=False)
    on_empty_stomach = models.BooleanField(default=False)
    
    # Reminder settings
    reminder_enabled = models.BooleanField(default=True)
    reminder_advance_minutes = models.IntegerField(
        default=0,
        help_text="Remind X minutes before scheduled time"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'medication_schedules'
        ordering = ['time_of_day']
    
    def __str__(self):
        return f"{self.medication.medication_name} at {self.time_of_day}"
    
    def should_remind_today(self):
        """Check if reminder should be sent today"""
        if not self.reminder_enabled or not self.is_active:
            return False
        
        if not self.days_of_week:
            return True  # Daily medication
        
        today = timezone.now().weekday()
        return today in self.days_of_week


class MedicationAdherence(models.Model):
    """
    Track medication adherence (taken/missed/skipped)
    One record per scheduled dose
    """
    
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('TAKEN', 'Taken'),
        ('MISSED', 'Missed'),
        ('SKIPPED', 'Skipped'),
        ('DELAYED', 'Delayed'),
    ]
    
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='adherence_records'
    )
    schedule = models.ForeignKey(
        MedicationSchedule,
        on_delete=models.CASCADE,
        related_name='adherence_records',
        null=True,
        blank=True
    )
    
    # Scheduled information
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    scheduled_datetime = models.DateTimeField()
    
    # Actual information
    actual_datetime = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Confirmation
    confirmed_by_patient = models.BooleanField(default=False)
    confirmation_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="'voice', 'app', 'manual_entry', 'auto_detected'"
    )
    
    # Reasons
    skip_reason = models.TextField(blank=True)
    miss_reason = models.TextField(blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    side_effects_reported = models.JSONField(default=list, blank=True)
    
    # Reminders
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'medication_adherence'
        ordering = ['-scheduled_datetime']
        indexes = [
            models.Index(fields=['medication', 'scheduled_date']),
            models.Index(fields=['status', 'scheduled_datetime']),
        ]
        unique_together = ['medication', 'scheduled_datetime']
    
    def __str__(self):
        return f"{self.medication.medication_name} - {self.scheduled_date} {self.scheduled_time} - {self.status}"
    
    @property
    def is_overdue(self):
        """Check if this dose is overdue"""
        if self.status != 'SCHEDULED':
            return False
        
        return timezone.now() > self.scheduled_datetime
    
    @property
    def current_status(self):
        """
        🤖 AI-FRIENDLY: Computed status (no periodic updates needed)
        
        Returns correct status based on current time.
        AI agent calls this when checking.
        """
        now = timezone.now()
        grace_period = timedelta(hours=1)
        
        # Already taken/skipped/missed - return as is
        if self.status in ['TAKEN', 'SKIPPED', 'MISSED']:
            return self.status
        
        # Scheduled - check if overdue
        if self.status == 'SCHEDULED':
            if self.scheduled_datetime < now - grace_period:
                return 'OVERDUE'  # Virtual status for AI
            elif self.scheduled_datetime < now:
                return 'IN_GRACE_PERIOD'  # Within grace period
            else:
                return 'SCHEDULED'  # Future
        
        return self.status
    
    def mark_as_missed_if_overdue(self):
        """
        Call this when AI agent detects overdue
        Only updates DB when actually needed
        """
        if self.is_overdue and self.status == 'SCHEDULED':
            self.status = 'MISSED'
            self.miss_reason = 'Marked as missed by AI agent after grace period'
            self.save()
            return True
        return False
    
    @property
    def delay_minutes(self):
        """Calculate delay in minutes if taken late"""
        if self.status == 'TAKEN' and self.actual_datetime:
            delta = self.actual_datetime - self.scheduled_datetime
            return int(delta.total_seconds() / 60)
        return None


class MedicationEscalation(models.Model):
    """
    Track escalation actions for missed medications
    """
    
    ACTION_CHOICES = [
        ('REMINDER_SENT', 'Reminder Sent'),
        ('FAMILY_NOTIFIED', 'Family Notified'),
        ('DOCTOR_NOTIFIED', 'Doctor Notified'),
        ('ALERT_CREATED', 'Alert Created'),
        ('CALL_INITIATED', 'Call Initiated'),
    ]
    
    adherence_record = models.ForeignKey(
        MedicationAdherence,
        on_delete=models.CASCADE,
        related_name='escalations'
    )
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='escalations'
    )
    
    action_taken = models.CharField(max_length=30, choices=ACTION_CHOICES)
    action_details = models.JSONField(
        default=dict,
        help_text="Details about the action: who was notified, call status, etc."
    )
    
    escalation_reason = models.TextField()
    consecutive_misses = models.IntegerField(default=1)
    
    successful = models.BooleanField(default=False)
    response_received = models.BooleanField(default=False)
    response_details = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'medication_escalations'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Escalation: {self.action_taken} for {self.medication.medication_name}"


class MedicationInteraction(models.Model):
    """
    Track potential drug interactions
    """
    
    SEVERITY_CHOICES = [
        ('MILD', 'Mild'),
        ('MODERATE', 'Moderate'),
        ('SEVERE', 'Severe'),
        ('CONTRAINDICATED', 'Contraindicated'),
    ]
    
    medication_1 = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='interactions_as_med1'
    )
    medication_2 = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='interactions_as_med2'
    )
    
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    description = models.TextField()
    clinical_effects = models.TextField(blank=True)
    management = models.TextField(
        blank=True,
        help_text="How to manage this interaction"
    )
    
    # Status
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    override_reason = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'medication_interactions'
        ordering = ['-severity', '-created_at']
        unique_together = ['medication_1', 'medication_2']
    
    def __str__(self):
        return f"{self.medication_1.medication_name} ↔ {self.medication_2.medication_name} ({self.severity})"


class MedicationRefill(models.Model):
    """
    Track medication refill requests and history
    """
    
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('FILLED', 'Filled'),
        ('READY', 'Ready for Pickup'),
        ('PICKED_UP', 'Picked Up'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='refill_requests'
    )
    
    requested_date = models.DateField(auto_now_add=True)
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='medication_refills_requested'
    )
    
    quantity = models.IntegerField()
    pharmacy_name = models.CharField(max_length=200, blank=True)
    pharmacy_phone = models.CharField(max_length=20, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REQUESTED')
    
    # Fulfillment
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medication_refills_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    filled_date = models.DateField(null=True, blank=True)
    pickup_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'medication_refills'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Refill for {self.medication.medication_name} - {self.status}"


class MedicationAdherencePattern(models.Model):
    """
    Computed adherence patterns and insights
    Generated by background tasks
    """
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='medication_patterns'
    )
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='adherence_patterns',
        null=True,
        blank=True
    )
    
    # Time period
    period_start = models.DateField()
    period_end = models.DateField()
    period_label = models.CharField(max_length=50)  # 'last_7days', 'last_30days'
    
    # Statistics
    total_scheduled = models.IntegerField(default=0)
    total_taken = models.IntegerField(default=0)
    total_missed = models.IntegerField(default=0)
    total_skipped = models.IntegerField(default=0)
    
    adherence_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage of doses taken on time"
    )
    
    # Patterns
    most_missed_time = models.TimeField(null=True, blank=True)
    most_missed_day = models.IntegerField(
        null=True,
        blank=True,
        help_text="0=Monday, 6=Sunday"
    )
    consecutive_misses_max = models.IntegerField(default=0)
    average_delay_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Average delay when taken late"
    )
    
    # Insights
    insights = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)
    
    computed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'medication_adherence_patterns'
        ordering = ['-period_end']
        unique_together = ['patient', 'medication', 'period_label', 'period_start']
    
    def __str__(self):
        med_name = self.medication.medication_name if self.medication else "All medications"
        return f"{self.patient.user.get_full_name()} - {med_name} - {self.period_label}"
