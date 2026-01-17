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
