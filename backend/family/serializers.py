from rest_framework import serializers
from django.utils import timezone
from .models import (
    FamilyMember, FamilyInvitation, FamilyNote,
    FamilyActivityLog, FamilyCommunication, CareSchedule,
    FamilyDashboardSettings
)
from users.models import User


class FamilyMemberSerializer(serializers.ModelSerializer):
    """Serializer for family members"""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.get_full_name', read_only=True)
    
    class Meta:
        model = FamilyMember
        fields = [
            'id', 'user', 'user_name', 'user_email', 'user_phone',
            'patient', 'patient_name', 'relationship', 'relationship_details',
            'access_level', 'can_view_vitals', 'can_view_medications',
            'can_view_alerts', 'can_view_medical_history',
            'can_acknowledge_alerts', 'can_add_notes',
            'can_manage_medications', 'can_invite_others',
            'is_primary_caregiver', 'is_emergency_contact', 'is_active',
            'invited_by', 'invited_by_name', 'invitation_accepted_at',
            'last_viewed_at', 'view_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invited_by', 'invitation_accepted_at',
            'last_viewed_at', 'view_count', 'created_at', 'updated_at'
        ]


class FamilyMemberListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing family members"""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = FamilyMember
        fields = [
            'id', 'user_name', 'patient_name', 'relationship',
            'access_level', 'is_primary_caregiver', 'is_active'
        ]


class FamilyInvitationSerializer(serializers.ModelSerializer):
    """Serializer for family invitations"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.get_full_name', read_only=True)
    accepted_by_name = serializers.CharField(source='accepted_by.get_full_name', read_only=True)
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = FamilyInvitation
        fields = [
            'id', 'patient', 'patient_name', 'invited_by', 'invited_by_name',
            'invitee_email', 'invitee_phone', 'invitee_name',
            'relationship', 'access_level', 'personal_message',
            'invitation_token', 'status', 'created_at', 'expires_at',
            'accepted_at', 'declined_at', 'accepted_by', 'accepted_by_name',
            'is_expired'
        ]
        read_only_fields = [
            'id', 'invitation_token', 'created_at', 'accepted_at',
            'declined_at', 'accepted_by'
        ]


class SendInvitationSerializer(serializers.Serializer):
    """Serializer for sending invitations"""
    
    invitee_email = serializers.EmailField(required=True)
    invitee_phone = serializers.CharField(required=False, allow_blank=True)
    invitee_name = serializers.CharField(required=False, allow_blank=True)
    relationship = serializers.ChoiceField(choices=FamilyMember.RELATIONSHIP_CHOICES)
    access_level = serializers.ChoiceField(
        choices=FamilyMember.ACCESS_LEVEL_CHOICES,
        default='BASIC'
    )
    personal_message = serializers.CharField(required=False, allow_blank=True)


class FamilyNoteSerializer(serializers.ModelSerializer):
    """Serializer for family notes"""
    
    author_name = serializers.CharField(source='family_member.user.get_full_name', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = FamilyNote
        fields = [
            'id', 'patient', 'patient_name', 'family_member', 'author_name',
            'note_type', 'title', 'content', 'related_vital_reading',
            'related_medication', 'related_alert', 'is_private',
            'is_important', 'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FamilyActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for activity logs"""
    
    user_name = serializers.CharField(source='family_member.user.get_full_name', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = FamilyActivityLog
        fields = [
            'id', 'family_member', 'user_name', 'patient', 'patient_name',
            'action', 'description', 'ip_address', 'related_object_type',
            'related_object_id', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class FamilyCommunicationSerializer(serializers.ModelSerializer):
    """Serializer for family communications"""
    
    sender_name = serializers.CharField(source='sender.user.get_full_name', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    reply_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FamilyCommunication
        fields = [
            'id', 'patient', 'patient_name', 'sender', 'sender_name',
            'message_type', 'subject', 'message', 'related_alert',
            'related_note', 'parent_message', 'read_by', 'reply_count',
            'created_at'
        ]
        read_only_fields = ['id', 'read_by', 'created_at']
    
    def get_reply_count(self, obj):
        return obj.replies.count()


class CareScheduleSerializer(serializers.ModelSerializer):
    """Serializer for care schedules"""
    
    assigned_to_name = serializers.CharField(source='assigned_to.user.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.user.get_full_name', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = CareSchedule
        fields = [
            'id', 'patient', 'patient_name', 'assigned_to', 'assigned_to_name',
            'created_by', 'created_by_name', 'schedule_type', 'title',
            'description', 'scheduled_date', 'scheduled_time',
            'duration_minutes', 'is_recurring', 'recurrence_pattern',
            'status', 'completed_at', 'completion_notes', 'send_reminder',
            'reminder_minutes_before', 'reminder_sent', 'is_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'reminder_sent', 'created_at', 'updated_at']


class MarkScheduleCompleteSerializer(serializers.Serializer):
    """Serializer for marking schedule as complete"""
    
    completion_notes = serializers.CharField(required=False, allow_blank=True)


class FamilyDashboardSettingsSerializer(serializers.ModelSerializer):
    """Serializer for dashboard settings"""
    
    class Meta:
        model = FamilyDashboardSettings
        fields = [
            'id', 'family_member', 'visible_widgets', 'widget_order',
            'default_time_range', 'show_vital_trends',
            'show_medication_adherence', 'show_alert_history',
            'notify_on_critical_alerts', 'notify_on_missed_medications',
            'notify_on_schedule_reminders', 'daily_summary_enabled',
            'daily_summary_time', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']


class FamilyDashboardSerializer(serializers.Serializer):
    """Serializer for family dashboard summary"""
    
    patient_name = serializers.CharField()
    patient_status = serializers.CharField()
    active_alerts_count = serializers.IntegerField()
    critical_alerts_count = serializers.IntegerField()
    medication_adherence_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    recent_vitals = serializers.DictField()
    upcoming_schedules = CareScheduleSerializer(many=True)
    unread_messages_count = serializers.IntegerField()
