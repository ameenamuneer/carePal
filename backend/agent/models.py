"""
AI Agent Module - Complete Models
Replaces the basic Conversation/Message models with full agent capabilities
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from patients.models import PatientProfile
import uuid


class AgentSession(models.Model):
    """
    Track AI agent conversation sessions with patients/family
    Replaces the simple Conversation model
    """
    
    SESSION_TYPE_CHOICES = [
        ('VOICE_CALL', 'Voice Call'),
        ('WEBSOCKET', 'WebSocket Chat'),
        ('SCHEDULED_CHECKIN', 'Scheduled Check-in'),
        ('EMERGENCY', 'Emergency Intervention'),
        ('FAMILY_QUERY', 'Family Member Query'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('TIMEOUT', 'Timeout'),
        ('ERROR', 'Error'),
        ('INTERRUPTED', 'Interrupted'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
        ('ml', 'Malayalam'),
        ('kn', 'Kannada'),
        ('bn', 'Bengali'),
    ]
    
    # Relationships
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='agent_sessions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agent_sessions',
        help_text="User who initiated (patient or family member)"
    )
    
    # Session details
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Cost tracking (Gemini 2.0 Flash)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    audio_input_seconds = models.IntegerField(default=0)
    audio_output_seconds = models.IntegerField(default=0)
    estimated_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0.000000,
        help_text="Estimated cost based on Gemini pricing"
    )
    
    # Context management
    context_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="What patient data was sent to AI for this session"
    )
    context_size_tokens = models.IntegerField(default=0)
    
    # Results
    outcome = models.CharField(
        max_length=200,
        blank=True,
        help_text="Summary of what was accomplished"
    )
    actions_taken_count = models.IntegerField(default=0)
    alerts_created = models.IntegerField(default=0)
    
    # Twilio integration (for voice calls)
    twilio_call_sid = models.CharField(max_length=100, blank=True)
    twilio_call_status = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional session metadata"
    )
    
    class Meta:
        db_table = 'agent_sessions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['patient', '-started_at']),
            models.Index(fields=['session_type', 'status']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.session_type} - {self.patient.user.get_full_name()} - {self.started_at}"
    
    def save(self, *args, **kwargs):
        """Auto-generate session_id if not provided"""
        if not self.session_id:
            # Generate unique session ID
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            unique_id = uuid.uuid4().hex[:8]
            self.session_id = f"session_{timestamp}_{unique_id}"
        
        super().save(*args, **kwargs)
    
    def calculate_duration(self):
        """Calculate and save session duration"""
        if self.ended_at:
            delta = self.ended_at - self.started_at
            self.duration_seconds = int(delta.total_seconds())
            self.save(update_fields=['duration_seconds'])
    
    def calculate_cost(self):
        """
        Calculate estimated cost based on Gemini 2.0 Flash pricing
        Input: $0.075 per 1M tokens
        Output: $0.30 per 1M tokens
        Audio: $0.50 per 1M tokens (approximated by seconds)
        """
        input_cost = (self.input_tokens / 1_000_000) * 0.075
        output_cost = (self.output_tokens / 1_000_000) * 0.30
        
        # Audio cost estimation (rough approximation)
        # Assume ~50 tokens per second of audio
        audio_input_cost = ((self.audio_input_seconds * 50) / 1_000_000) * 0.50
        audio_output_cost = ((self.audio_output_seconds * 50) / 1_000_000) * 0.50
        
        self.estimated_cost_usd = input_cost + output_cost + audio_input_cost + audio_output_cost
        self.save(update_fields=['estimated_cost_usd'])
        
        return float(self.estimated_cost_usd)


class AgentMessage(models.Model):
    """
    Individual messages within an agent session
    Enhanced version of the Message model
    """
    
    SENDER_CHOICES = [
        ('USER', 'User'),
        ('AGENT', 'AI Agent'),
        ('SYSTEM', 'System'),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('TEXT', 'Text'),
        ('AUDIO', 'Audio'),
        ('FUNCTION_CALL', 'Function Call'),
        ('FUNCTION_RESULT', 'Function Result'),
        ('SYSTEM_EVENT', 'System Event'),
    ]
    
    session = models.ForeignKey(
        AgentSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    # Message details
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='TEXT')
    content = models.TextField()
    
    # Audio-specific fields
    audio_duration_seconds = models.IntegerField(null=True, blank=True)
    audio_url = models.URLField(max_length=500, blank=True)
    
    # Function calling
    function_name = models.CharField(max_length=100, blank=True)
    function_parameters = models.JSONField(default=dict, blank=True)
    function_result = models.JSONField(default=dict, blank=True)
    
    # Token usage for this message
    tokens = models.IntegerField(default=0)
    
    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'agent_messages'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.sender}: {self.content[:50]}"


class AgentAction(models.Model):
    """
    Actions taken by AI agent via function calling
    """
    
    ACTION_TYPE_CHOICES = [
        ('CREATE_ALERT', 'Create Alert'),
        ('UPDATE_MEDICATION', 'Update Medication'),
        ('RECORD_VITAL', 'Record Vital Sign'),
        ('CALL_EMERGENCY', 'Call Emergency Contact'),
        ('CALL_FAMILY', 'Call Family Member'),
        ('SEND_SMS', 'Send SMS'),
        ('SCHEDULE_TASK', 'Schedule Task'),
        ('LOG_ACTIVITY', 'Log Activity'),
        ('UPDATE_PATIENT', 'Update Patient Info'),
        ('QUERY_DATA', 'Query Patient Data'),
        ('GENERATE_REPORT', 'Generate Report'),
        ('MEDICATION_REMINDER', 'Send Medication Reminder'),
        ('ESCALATE_ALERT', 'Escalate Alert'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('BLOCKED', 'Blocked by Permission'),
    ]
    
    session = models.ForeignKey(
        AgentSession,
        on_delete=models.CASCADE,
        related_name='actions'
    )
    
    # Action details
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)
    function_called = models.CharField(max_length=100)
    parameters = models.JSONField(
        default=dict,
        help_text="Parameters passed to the function"
    )
    
    # Results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    result = models.JSONField(
        default=dict,
        blank=True,
        help_text="Result returned from the function"
    )
    error_message = models.TextField(blank=True)
    
    # Permissions
    requires_permission = models.BooleanField(default=True)
    permission_granted = models.BooleanField(default=False)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_agent_actions'
    )
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'agent_actions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', '-created_at']),
            models.Index(fields=['action_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.action_type} - {self.status}"


class AgentMemory(models.Model):
    """
    Persistent memory for continuity across sessions
    """
    
    MEMORY_TYPE_CHOICES = [
        ('PREFERENCE', 'User Preference'),
        ('CONCERN', 'Health Concern'),
        ('INSTRUCTION', 'Special Instruction'),
        ('CONTEXT', 'Conversation Context'),
        ('GOAL', 'Health Goal'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='agent_memories'
    )
    
    # Memory details
    memory_type = models.CharField(max_length=20, choices=MEMORY_TYPE_CHOICES)
    key = models.CharField(max_length=200, help_text="Memory key/identifier")
    content = models.TextField()
    
    # Context
    source_session = models.ForeignKey(
        AgentSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='memories_created'
    )
    
    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Memory expires after this time (null = never)"
    )
    is_active = models.BooleanField(default=True)
    
    # Usage tracking
    access_count = models.IntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'agent_memories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'memory_type']),
            models.Index(fields=['key']),
        ]
        unique_together = ['patient', 'key']
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.memory_type}: {self.key}"
    
    def is_expired(self):
        """Check if memory has expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def record_access(self):
        """Record that this memory was accessed"""
        self.access_count += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=['access_count', 'last_accessed_at'])


class AgentEventLog(models.Model):
    """
    Log all agent events for monitoring and debugging
    """
    
    EVENT_TYPE_CHOICES = [
        ('SESSION_STARTED', 'Session Started'),
        ('SESSION_ENDED', 'Session Ended'),
        ('MESSAGE_SENT', 'Message Sent'),
        ('MESSAGE_RECEIVED', 'Message Received'),
        ('FUNCTION_CALLED', 'Function Called'),
        ('ACTION_EXECUTED', 'Action Executed'),
        ('ERROR_OCCURRED', 'Error Occurred'),
        ('ESCALATION_TRIGGERED', 'Escalation Triggered'),
        ('MEMORY_CREATED', 'Memory Created'),
        ('MEMORY_ACCESSED', 'Memory Accessed'),
    ]
    
    session = models.ForeignKey(
        AgentSession,
        on_delete=models.CASCADE,
        related_name='event_logs',
        null=True,
        blank=True
    )
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='agent_event_logs'
    )
    
    # Event details
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    event_data = models.JSONField(
        default=dict,
        help_text="Detailed event information"
    )
    
    # Severity (for errors)
    severity = models.CharField(
        max_length=20,
        choices=[
            ('DEBUG', 'Debug'),
            ('INFO', 'Info'),
            ('WARNING', 'Warning'),
            ('ERROR', 'Error'),
            ('CRITICAL', 'Critical'),
        ],
        default='INFO'
    )
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'agent_event_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['patient', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['session', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.patient.user.get_full_name()} - {self.timestamp}"


class PatientActivityLog(models.Model):
    """
    Structured log of patient activities and observations captured by the AI
    during natural conversation — not from direct enquiry.
    """

    ACTIVITY_TYPE_CHOICES = [
        ('MEAL', 'Meal / Eating'),
        ('EXERCISE', 'Physical Activity / Exercise'),
        ('SLEEP', 'Sleep / Rest'),
        ('SYMPTOM', 'Symptom Reported'),
        ('MEDICATION', 'Medication Related'),
        ('MOOD', 'Mood / Emotional State'),
        ('VITAL_OBSERVATION', 'Vital Sign Observation'),
        ('BEHAVIOR', 'Behavioral Pattern'),
        ('SOCIAL', 'Social Activity'),
        ('ENVIRONMENT', 'Environment / Location'),
        ('OTHER', 'Other'),
    ]

    CONFIDENCE_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    session = models.ForeignKey(
        AgentSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs'
    )

    # Core log fields
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField(
        help_text="Natural-language log entry, e.g. 'Patient had lunch at 2:30 pm'"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured additional details (meal items, symptom severity, etc.)"
    )

    # Timing — when the activity actually occurred vs when it was logged
    observed_at = models.DateTimeField(
        help_text="When the activity occurred (as reported/observed)"
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    # Snapshot of the latest vitals at the time of logging
    vitals_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Patient's most-recent vitals at the moment of logging"
    )

    # AI meta
    ai_confidence = models.CharField(
        max_length=6,
        choices=CONFIDENCE_CHOICES,
        default='MEDIUM'
    )
    is_notable = models.BooleanField(
        default=False,
        help_text="AI flagged this as unusual or worth clinician attention"
    )
    notable_reason = models.TextField(blank=True)

    # Free-form tags for filtering (e.g. ["dizziness", "skipped_walk"])
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'patient_activity_logs'
        ordering = ['-observed_at']
        indexes = [
            models.Index(fields=['patient', '-observed_at']),
            models.Index(fields=['activity_type', '-observed_at']),
            models.Index(fields=['is_notable', '-observed_at']),
            models.Index(fields=['session']),
        ]

    def __str__(self):
        return f"{self.patient.user.get_full_name()} | {self.activity_type} | {self.observed_at:%Y-%m-%d %H:%M}"


class AgentCacheEntry(models.Model):
    """
    Cache frequently used responses to reduce API costs
    """
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='agent_cache',
        null=True,
        blank=True,
        help_text="Patient-specific cache, null for global cache"
    )
    
    # Cache key
    cache_key = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Hash of the query/context"
    )
    
    # Cached data
    query = models.TextField(help_text="Original query")
    response = models.TextField(help_text="Cached response")
    context_hash = models.CharField(
        max_length=64,
        help_text="Hash of context used"
    )
    
    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    
    # Usage
    hit_count = models.IntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    
    # Savings
    tokens_saved = models.IntegerField(default=0)
    cost_saved_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0.000000
    )
    
    class Meta:
        db_table = 'agent_cache'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cache_key', 'expires_at']),
            models.Index(fields=['patient', 'cache_key']),
        ]
    
    def __str__(self):
        return f"Cache: {self.cache_key} ({self.hit_count} hits)"
    
    def is_valid(self):
        """Check if cache entry is still valid"""
        return timezone.now() < self.expires_at
    
    def record_hit(self, tokens_saved):
        """Record a cache hit"""
        self.hit_count += 1
        self.last_hit_at = timezone.now()
        self.tokens_saved += tokens_saved

        # Calculate cost savings (Gemini 2.0 Flash pricing)
        self.cost_saved_usd += (tokens_saved / 1_000_000) * 0.075
        self.save(update_fields=['hit_count', 'last_hit_at', 'tokens_saved', 'cost_saved_usd'])


class PendingQuestion(models.Model):
    """
    A question or prompt queued by a backend agent or process to be
    asked by the Live AI during the patient's next session.

    Reusable: any backend agent inserts a row here. The Live AI
    reads and clears pending questions at session start.
    """
    SOURCE_CHOICES = [
        ('MEDICATION_AGENT', 'Medication Monitor Agent'),
        ('NUTRITION_AGENT', 'Nutrition Monitor Agent'),
        ('SYSTEM', 'System'),
        ('DOCTOR', 'Doctor'),
        ('FAMILY', 'Family Member'),
    ]

    patient = models.ForeignKey(
        'patients.PatientProfile',
        on_delete=models.CASCADE,
        related_name='pending_questions',
    )
    question = models.TextField(
        help_text="The exact question or prompt to inject into the Live AI session."
    )
    context = models.TextField(
        blank=True,
        help_text="Internal context for why this question is being asked. "
                  "Not shown to the patient — used to help the AI frame the question naturally."
    )
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default='SYSTEM')
    source_object_type = models.CharField(
        max_length=50, blank=True,
        help_text="Optional: model name of the object that triggered this question."
    )
    source_object_id = models.IntegerField(
        null=True, blank=True,
        help_text="Optional: PK of the triggering object for audit trail."
    )
    priority = models.IntegerField(
        default=5,
        help_text="1 = highest priority (ask first), 10 = lowest. "
                  "Live AI asks pending questions in priority order."
    )
    asked = models.BooleanField(default=False)
    asked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="If the question is still pending after this time, discard it."
    )

    class Meta:
        db_table = 'pending_questions'
        ordering = ['priority', 'created_at']

    def __str__(self):
        return f"[{self.source}] {self.question[:60]}"


class NutritionLog(models.Model):
    MEAL_TYPE_CHOICES = [
        ('BREAKFAST', 'Breakfast'),
        ('LUNCH', 'Lunch'),
        ('DINNER', 'Dinner'),
        ('SNACK', 'Snack'),
        ('OTHER', 'Other'),
    ]

    patient = models.ForeignKey(
        'patients.PatientProfile',
        on_delete=models.CASCADE,
        related_name='nutrition_logs',
    )
    meal_time = models.DateTimeField(
        help_text="When the meal was consumed (may differ from when it was logged)"
    )
    meal_type = models.CharField(max_length=15, choices=MEAL_TYPE_CHOICES, default='OTHER')
    description = models.TextField(help_text="What the patient said they ate")
    estimated_kcal = models.IntegerField(
        null=True, blank=True,
        help_text="AI-estimated kilocalories for this meal",
    )
    items = models.JSONField(
        default=list, blank=True,
        help_text="Parsed food items: [{'name': 'rice', 'qty': '1 cup', 'kcal': 200}]",
    )
    appetite = models.CharField(
        max_length=10, blank=True,
        help_text="GOOD | POOR | NORMAL — patient's reported appetite",
    )
    below_threshold = models.BooleanField(
        default=False,
        help_text="True if daily total was below patient threshold when this log was saved",
    )
    # Audit trail — mirrors MedicationAdherence.source_activity_log
    source_activity_log = models.OneToOneField(
        'agent.PatientActivityLog',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nutrition_log',
        help_text="The MEAL activity log entry that triggered this record",
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'nutrition_logs'
        ordering = ['-meal_time']
        indexes = [models.Index(fields=['patient', '-meal_time'])]

    def __str__(self):
        return (
            f"{self.patient.user.get_full_name()} | "
            f"{self.meal_type} | {self.meal_time:%Y-%m-%d %H:%M}"
        )
