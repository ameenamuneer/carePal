from django.contrib import admin
from django.utils.html import format_html
from .models import (
    FamilyMember, FamilyInvitation, FamilyNote,
    FamilyActivityLog, FamilyCommunication, CareSchedule,
    FamilyDashboardSettings
)


@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'patient', 'relationship',
        'access_level', 'is_primary_caregiver',
        'is_active', 'created_at'
    ]
    list_filter = [
        'relationship', 'access_level', 'is_primary_caregiver',
        'is_active', 'created_at'
    ]
    search_fields = [
        'user__first_name', 'user__last_name',
        'patient__user__first_name', 'patient__user__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'last_viewed_at', 'view_count']
    
    fieldsets = (
        ('Relationship', {
            'fields': ('user', 'patient', 'relationship', 'relationship_details')
        }),
        ('Access Control', {
            'fields': ('access_level',)
        }),
        ('Permissions', {
            'fields': (
                'can_view_vitals', 'can_view_medications', 'can_view_alerts',
                'can_view_medical_history', 'can_acknowledge_alerts',
                'can_add_notes', 'can_manage_medications', 'can_invite_others'
            )
        }),
        ('Status', {
            'fields': ('is_primary_caregiver', 'is_emergency_contact', 'is_active')
        }),
        ('Invitation Tracking', {
            'fields': ('invited_by', 'invitation_accepted_at')
        }),
        ('Activity Tracking', {
            'fields': ('last_viewed_at', 'view_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(FamilyInvitation)
class FamilyInvitationAdmin(admin.ModelAdmin):
    list_display = [
        'invitee_email', 'patient', 'relationship',
        'status_badge', 'invited_by', 'created_at',
        'expires_at'
    ]
    list_filter = ['status', 'relationship', 'created_at']
    search_fields = [
        'invitee_email', 'invitee_name', 'patient__user__first_name']
    readonly_fields = [
        'invitation_token', 'created_at', 'accepted_at',
        'declined_at', 'is_expired'
    ]
    
    fieldsets = (
        ('Patient & Inviter', {
            'fields': ('patient', 'invited_by')
        }),
        ('Invitee Information', {
            'fields': ('invitee_email', 'invitee_phone', 'invitee_name')
        }),
        ('Invitation Details', {
            'fields': ('relationship', 'access_level', 'personal_message')
        }),
        ('Token', {
            'fields': ('invitation_token',)
        }),
        ('Status', {
            'fields': ('status', 'is_expired')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'expires_at', 'accepted_at', 'declined_at')
        }),
        ('Acceptance', {
            'fields': ('accepted_by',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'orange',
            'ACCEPTED': 'green',
            'DECLINED': 'red',
            'EXPIRED': 'gray',
            'CANCELLED': 'lightgray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(FamilyNote)
class FamilyNoteAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'patient', 'family_member',
        'note_type', 'is_important', 'is_private',
        'created_at'
    ]
    list_filter = ['note_type', 'is_important', 'is_private', 'created_at']
    search_fields = [
        'title', 'content',
        'patient__user__first_name',
        'family_member__user__first_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Note Information', {
            'fields': ('patient', 'family_member', 'note_type', 'title', 'content')
        }),
        ('Related Objects', {
            'fields': ('related_vital_reading', 'related_medication', 'related_alert')
        }),
        ('Settings', {
            'fields': ('is_private', 'is_important', 'attachments')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(FamilyActivityLog)
class FamilyActivityLogAdmin(admin.ModelAdmin):
    list_display = [
        'family_member', 'patient', 'action',
        'created_at', 'ip_address'
    ]
    list_filter = ['action', 'created_at']
    search_fields = [
        'family_member__user__first_name',
        'patient__user__first_name',
        'description'
    ]
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Activity', {
            'fields': ('family_member', 'patient', 'action', 'description')
        }),
        ('Context', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Related Object', {
            'fields': ('related_object_type', 'related_object_id')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(FamilyCommunication)
class FamilyCommunicationAdmin(admin.ModelAdmin):
    list_display = [
        'subject', 'sender', 'patient',
        'message_type', 'created_at'
    ]
    list_filter = ['message_type', 'created_at']
    search_fields = [
        'subject', 'message',
        'sender__user__first_name',
        'patient__user__first_name'
    ]
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Message Information', {
            'fields': ('patient', 'sender', 'message_type', 'subject', 'message')
        }),
        ('Related Objects', {
            'fields': ('related_alert', 'related_note', 'parent_message')
        }),
        ('Read Tracking', {
            'fields': ('read_by',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(CareSchedule)
class CareScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'patient', 'assigned_to',
        'schedule_type', 'scheduled_date',
        'status_badge', 'is_overdue'
    ]
    list_filter = ['schedule_type', 'status', 'scheduled_date', 'is_recurring']
    search_fields = [
        'title', 'description',
        'patient__user__first_name',
        'assigned_to__user__first_name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'is_overdue', 'reminder_sent']
    
    fieldsets = (
        ('Schedule Information', {
            'fields': (
                'patient', 'assigned_to', 'created_by',
                'schedule_type', 'title', 'description'
            )
        }),
        ('Timing', {
            'fields': (
                'scheduled_date', 'scheduled_time', 'duration_minutes',
                'is_recurring', 'recurrence_pattern'
            )
        }),
        ('Status', {
            'fields': (
                'status', 'completed_at', 'completion_notes', 'is_overdue'
            )
        }),
        ('Reminders', {
            'fields': (
                'send_reminder', 'reminder_minutes_before', 'reminder_sent'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'SCHEDULED': 'blue',
            'IN_PROGRESS': 'orange',
            'COMPLETED': 'green',
            'CANCELLED': 'gray',
            'MISSED': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(FamilyDashboardSettings)
class FamilyDashboardSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'family_member', 'default_time_range',
        'daily_summary_enabled', 'updated_at'
    ]
    list_filter = ['daily_summary_enabled', 'updated_at']
    search_fields = ['family_member__user__first_name']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Family Member', {
            'fields': ('family_member',)
        }),
        ('Widget Preferences', {
            'fields': ('visible_widgets', 'widget_order')
        }),
        ('Data Preferences', {
            'fields': (
                'default_time_range', 'show_vital_trends',
                'show_medication_adherence', 'show_alert_history'
            )
        }),
        ('Notification Preferences', {
            'fields': (
                'notify_on_critical_alerts', 'notify_on_missed_medications',
                'notify_on_schedule_reminders', 'daily_summary_enabled',
                'daily_summary_time'
            )
        }),
        ('Metadata', {
            'fields': ('updated_at',)
        }),
    )
