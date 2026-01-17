from django.contrib import admin
from django.utils.html import format_html
from .models import (
    CloudProvider, CloudAPICredential, DeviceSyncLog,
    DeviceCalibration, DataConflict, WebhookSubscription,
    BluetoothDeviceSession, DevicePriority
)


@admin.register(CloudProvider)
class CloudProviderAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'name', 'is_active',
        'sync_interval_minutes', 'supports_webhooks'
    ]
    list_filter = ['is_active', 'supports_webhooks']
    search_fields = ['display_name', 'name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'is_active')
        }),
        ('OAuth Configuration', {
            'fields': (
                'client_id', 'client_secret', 'authorization_url',
                'token_url', 'api_base_url', 'scopes'
            )
        }),
        ('Configuration', {
            'fields': (
                'supports_webhooks', 'webhook_url', 'rate_limit_per_hour',
                'sync_interval_minutes', 'supported_vitals'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(CloudAPICredential)
class CloudAPICredentialAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'provider', 'status_badge',
        'last_sync_at', 'expires_at', 'is_token_expired'
    ]
    list_filter = ['status', 'provider', 'created_at']
    search_fields = ['patient__user__first_name', 'provider__display_name']
    readonly_fields = [
        'created_at', 'updated_at', 'consent_given_at',
        'is_token_expired', 'needs_refresh'
    ]
    
    fieldsets = (
        ('Patient & Provider', {
            'fields': ('patient', 'provider', 'data_source')
        }),
        ('Token Information', {
            'fields': (
                'token_type', 'expires_at', 'scope',
                'is_token_expired', 'needs_refresh'
            )
        }),
        ('Provider User Info', {
            'fields': ('provider_user_id', 'provider_user_info')
        }),
        ('Status', {
            'fields': ('status', 'last_sync_at', 'last_error')
        }),
        ('Consent', {
            'fields': ('consent_given_at', 'consent_revoked_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'ACTIVE': 'green',
            'EXPIRED': 'orange',
            'REVOKED': 'red',
            'ERROR': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(DeviceSyncLog)
class DeviceSyncLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'data_source', 'sync_type', 'started_at',
        'status_badge', 'duration_seconds', 'records_created',
        'records_failed'
    ]
    list_filter = ['status', 'sync_type', 'started_at']
    search_fields = ['data_source__device_name']
    readonly_fields = ['started_at', 'completed_at', 'duration_seconds']
    
    fieldsets = (
        ('Device', {
            'fields': ('data_source', 'cloud_credential')
        }),
        ('Sync Details', {
            'fields': (
                'sync_type', 'started_at', 'completed_at',
                'duration_seconds', 'status'
            )
        }),
        ('Results', {
            'fields': (
                'records_fetched', 'records_created',
                'records_updated', 'records_failed'
            )
        }),
        ('Time Range', {
            'fields': ('sync_from_date', 'sync_to_date')
        }),
        ('Error Details', {
            'fields': ('error_message', 'error_details')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'STARTED': 'blue',
            'SUCCESS': 'green',
            'PARTIAL': 'orange',
            'FAILED': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(DeviceCalibration)
class DeviceCalibrationAdmin(admin.ModelAdmin):
    list_display = [
        'data_source', 'calibrated_at', 'calibration_type',
        'deviation', 'is_active'
    ]
    list_filter = ['calibration_type', 'is_active', 'calibrated_at']
    search_fields = ['data_source__device_name']
    readonly_fields = ['created_at']


@admin.register(DataConflict)
class DataConflictAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'vital_type', 'conflict_time',
        'max_deviation', 'resolution_method', 'resolved_at'
    ]
    list_filter = ['resolution_method', 'vital_type', 'conflict_time']
    search_fields = ['patient__user__first_name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Conflict Details', {
            'fields': (
                'patient', 'vital_type', 'conflict_time',
                'time_window_minutes'
            )
        }),
        ('Readings', {
            'fields': ('readings', 'max_deviation', 'deviation_percentage')
        }),
        ('Resolution', {
            'fields': (
                'resolution_method', 'selected_reading_id',
                'resolved_value', 'resolved_by', 'resolved_at',
                'resolution_notes'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )


@admin.register(BluetoothDeviceSession)
class BluetoothDeviceSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id', 'data_source', 'connected_at',
        'duration_seconds', 'status', 'readings_received',
        'battery_level'
    ]
    list_filter = ['status', 'connected_at']
    search_fields = ['session_id', 'data_source__device_name']
    readonly_fields = ['connected_at']


@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'subscription_id', 'cloud_credential', 'status',
        'verified_at', 'notification_count', 'expires_at'
    ]
    list_filter = ['status', 'verified_at']
    search_fields = ['subscription_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DevicePriority)
class DevicePriorityAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'vital_type', 'use_average_if_close',
        'threshold_percentage'
    ]
    list_filter = ['vital_type', 'use_average_if_close']
    search_fields = ['patient__user__first_name']
    readonly_fields = ['updated_at']
