"""
AI Agent Module - Serializers
"""

from rest_framework import serializers
from .models import (
    AgentSession,
    AgentMessage,
    AgentAction,
    AgentMemory,
    AgentEventLog,
    AgentCacheEntry,
    PatientActivityLog,
)


class AgentMessageSerializer(serializers.ModelSerializer):
    """Serializer for agent messages"""
    
    class Meta:
        model = AgentMessage
        fields = [
            'id', 'session', 'sender', 'message_type', 'content',
            'audio_duration_seconds', 'audio_url',
            'function_name', 'function_parameters', 'function_result',
            'tokens', 'timestamp', 'metadata'
        ]
        read_only_fields = ['id', 'timestamp', 'tokens']


class AgentActionSerializer(serializers.ModelSerializer):
    """Serializer for agent actions"""
    
    granted_by_name = serializers.CharField(
        source='granted_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = AgentAction
        fields = [
            'id', 'session', 'action_type', 'function_called',
            'parameters', 'status', 'result', 'error_message',
            'requires_permission', 'permission_granted',
            'granted_by', 'granted_by_name',
            'created_at', 'executed_at', 'metadata'
        ]
        read_only_fields = ['id', 'created_at', 'executed_at']


class AgentSessionSerializer(serializers.ModelSerializer):
    """Serializer for agent sessions"""
    
    patient_name = serializers.CharField(
        source='patient.user.get_full_name',
        read_only=True
    )
    user_name = serializers.CharField(
        source='user.get_full_name',
        read_only=True
    )
    messages = AgentMessageSerializer(many=True, read_only=True)
    actions = AgentActionSerializer(many=True, read_only=True)
    
    class Meta:
        model = AgentSession
        fields = [
            'id', 'session_id', 'patient', 'patient_name',
            'user', 'user_name', 'session_type', 'status', 'language',
            'started_at', 'ended_at', 'duration_seconds',
            'input_tokens', 'output_tokens',
            'audio_input_seconds', 'audio_output_seconds',
            'estimated_cost_usd', 'context_snapshot', 'context_size_tokens',
            'outcome', 'actions_taken_count', 'alerts_created',
            'twilio_call_sid', 'twilio_call_status', 'phone_number',
            'metadata', 'messages', 'actions'
        ]
        read_only_fields = [
            'id', 'started_at', 'duration_seconds',
            'input_tokens', 'output_tokens',
            'audio_input_seconds', 'audio_output_seconds',
            'estimated_cost_usd', 'actions_taken_count', 'alerts_created'
        ]


class AgentSessionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for session lists"""
    
    patient_name = serializers.CharField(
        source='patient.user.get_full_name',
        read_only=True
    )
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AgentSession
        fields = [
            'id', 'session_id', 'patient', 'patient_name',
            'session_type', 'status', 'language',
            'started_at', 'ended_at', 'duration_seconds',
            'estimated_cost_usd', 'outcome',
            'message_count', 'actions_taken_count'
        ]
    
    def get_message_count(self, obj):
        return obj.messages.count()


class AgentMemorySerializer(serializers.ModelSerializer):
    """Serializer for agent memories"""
    
    patient_name = serializers.CharField(
        source='patient.user.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = AgentMemory
        fields = [
            'id', 'patient', 'patient_name', 'memory_type',
            'key', 'content', 'source_session',
            'created_at', 'updated_at', 'expires_at', 'is_active',
            'access_count', 'last_accessed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'access_count', 'last_accessed_at']


class AgentEventLogSerializer(serializers.ModelSerializer):
    """Serializer for event logs"""
    
    patient_name = serializers.CharField(
        source='patient.user.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = AgentEventLog
        fields = [
            'id', 'session', 'patient', 'patient_name',
            'event_type', 'event_data', 'severity', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class AgentCacheEntrySerializer(serializers.ModelSerializer):
    """Serializer for cache entries"""
    
    class Meta:
        model = AgentCacheEntry
        fields = [
            'id', 'patient', 'cache_key', 'query', 'response',
            'context_hash', 'created_at', 'expires_at',
            'hit_count', 'last_hit_at', 'tokens_saved', 'cost_saved_usd'
        ]
        read_only_fields = ['id', 'created_at', 'hit_count', 'last_hit_at', 'tokens_saved', 'cost_saved_usd']


class PatientActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for patient activity logs captured by the AI"""

    patient_name = serializers.CharField(
        source='patient.user.get_full_name',
        read_only=True
    )
    session_id = serializers.CharField(
        source='session.session_id',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = PatientActivityLog
        fields = [
            'id', 'patient', 'patient_name', 'session', 'session_id',
            'activity_type', 'description', 'details',
            'observed_at', 'logged_at',
            'vitals_snapshot',
            'ai_confidence', 'is_notable', 'notable_reason', 'tags',
        ]
        read_only_fields = ['id', 'logged_at', 'vitals_snapshot', 'patient_name', 'session_id']


# WebSocket Message Formats

class WebSocketMessageInputSerializer(serializers.Serializer):
    """Serializer for incoming WebSocket messages"""
    
    message = serializers.CharField(required=False, allow_blank=True)
    audio_data = serializers.CharField(required=False, allow_blank=True, help_text="Base64 encoded audio")
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    language = serializers.ChoiceField(
        choices=['en', 'hi', 'ta', 'te', 'ml', 'kn', 'bn'],
        required=False,
        default='en'
    )
    metadata = serializers.JSONField(required=False, default=dict)


class WebSocketMessageOutputSerializer(serializers.Serializer):
    """Serializer for outgoing WebSocket messages"""
    
    message = serializers.CharField()
    sender = serializers.CharField()
    audio_url = serializers.URLField(required=False, allow_null=True)
    function_call = serializers.DictField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField()
    metadata = serializers.DictField(required=False, default=dict)
