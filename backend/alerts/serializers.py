from rest_framework import serializers
from django.utils import timezone
from .models import (
    AlertType, Alert, AlertDelivery, AlertRule,
    NotificationPreference, AlertEscalation, AlertTemplate,
    AlertStatistics
)


class AlertTypeSerializer(serializers.ModelSerializer):
    """Serializer for alert types catalog"""
    
    class Meta:
        model = AlertType
        fields = [
            'id', 'code', 'name', 'category', 'default_severity',
            'message_template', 'default_channels', 'requires_acknowledgment',
            'auto_escalate_minutes', 'allow_grouping', 'grouping_window_minutes',
            'is_active'
        ]
        read_only_fields = ['id']


class AlertDeliverySerializer(serializers.ModelSerializer):
    """Serializer for alert deliveries"""
    
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)
    
    class Meta:
        model = AlertDelivery
        fields = [
            'id', 'alert', 'recipient', 'recipient_name', 'channel',
            'recipient_address', 'status', 'created_at', 'sent_at',
            'delivered_at', 'read_at', 'error_message', 'retry_count',
            'external_id'
        ]
        read_only_fields = ['id', 'created_at']


class AlertSerializer(serializers.ModelSerializer):
    """Full alert serializer"""
    
    alert_type_detail = AlertTypeSerializer(source='alert_type', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    deliveries = AlertDeliverySerializer(many=True, read_only=True)
    is_expired = serializers.ReadOnlyField()
    needs_escalation = serializers.ReadOnlyField()
    
    class Meta:
        model = Alert
        fields = [
            'id', 'alert_type', 'alert_type_detail', 'patient', 'patient_name',
            'severity', 'title', 'message', 'vital_reading', 'medication_adherence',
            'data_source', 'context_data', 'status', 'created_at', 'sent_at',
            'delivered_at', 'acknowledged_at', 'resolved_at', 'expires_at',
            'acknowledged_by', 'acknowledged_by_name', 'acknowledgment_notes',
            'resolved_by', 'resolved_by_name', 'resolution_notes',
            'is_escalated', 'escalated_at', 'escalation_level',
            'parent_alert', 'is_grouped', 'grouped_count',
            'deliveries', 'is_expired', 'needs_escalation', 'metadata'
        ]
        read_only_fields = [
            'id', 'created_at', 'sent_at', 'delivered_at',
            'is_escalated', 'escalated_at'
        ]


class AlertListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing alerts"""
    
    alert_type_name = serializers.CharField(source='alert_type.name', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = Alert
        fields = [
            'id', 'alert_type_name', 'patient_name', 'severity',
            'title', 'status', 'created_at', 'is_escalated',
            'is_grouped', 'grouped_count'
        ]


class AlertAcknowledgeSerializer(serializers.Serializer):
    """Serializer for acknowledging alerts"""
    
    acknowledgment_notes = serializers.CharField(required=False, allow_blank=True)


class AlertResolveSerializer(serializers.Serializer):
    """Serializer for resolving alerts"""
    
    resolution_notes = serializers.CharField(required=True)


class AlertRuleSerializer(serializers.ModelSerializer):
    """Serializer for alert rules"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    alert_type_name = serializers.CharField(source='alert_type.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertRule
        fields = [
            'id', 'patient', 'patient_name', 'alert_type', 'alert_type_name',
            'name', 'description', 'rule_type', 'conditions',
            'override_severity', 'custom_message', 'delivery_channels',
            'notify_patient', 'notify_family', 'notify_doctor',
            'additional_recipients', 'active_hours_start', 'active_hours_end',
            'active_days', 'max_alerts_per_hour', 'cooldown_minutes',
            'is_active', 'last_triggered_at', 'trigger_count',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'last_triggered_at', 'trigger_count', 'created_at', 'updated_at'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences"""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'user_name', 'enable_in_app', 'enable_push',
            'enable_sms', 'enable_email', 'enable_voice_call',
            'receive_info', 'receive_warning', 'receive_critical',
            'receive_emergency', 'category_preferences',
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
            'quiet_hours_exceptions', 'sms_phone_number', 'voice_call_number',
            'email_address', 'push_device_tokens', 'enable_daily_digest',
            'digest_time', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']


class AlertEscalationSerializer(serializers.ModelSerializer):
    """Serializer for alert escalations"""
    
    escalated_by_name = serializers.CharField(source='escalated_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertEscalation
        fields = [
            'id', 'alert', 'escalation_type', 'escalation_level',
            'trigger_reason', 'previous_severity', 'new_severity',
            'additional_recipients', 'additional_channels',
            'escalated_by', 'escalated_by_name', 'escalated_at'
        ]
        read_only_fields = ['id', 'escalated_at']


class AlertStatisticsSerializer(serializers.ModelSerializer):
    """Serializer for alert statistics"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = AlertStatistics
        fields = [
            'id', 'patient', 'patient_name', 'period_start', 'period_end',
            'period_label', 'total_alerts', 'info_count', 'warning_count',
            'critical_count', 'emergency_count', 'vital_anomaly_count',
            'medication_count', 'device_count', 'health_trend_count',
            'avg_acknowledgment_time_minutes', 'avg_resolution_time_minutes',
            'escalation_count', 'unacknowledged_count', 'insights',
            'computed_at'
        ]


class AlertDashboardSerializer(serializers.Serializer):
    """Serializer for alert dashboard summary"""
    
    total_active = serializers.IntegerField()
    critical_count = serializers.IntegerField()
    emergency_count = serializers.IntegerField()
    unacknowledged_count = serializers.IntegerField()
    escalated_count = serializers.IntegerField()
    recent_alerts = AlertListSerializer(many=True)
    alerts_by_severity = serializers.DictField()
    alerts_by_category = serializers.DictField()
