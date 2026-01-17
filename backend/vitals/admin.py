from django.contrib import admin
from django.utils.html import format_html
from .models import (
    VitalType, DataSource, VitalReading,
    VitalReadingEdit, ContinuousVitalSession, VitalTrendAnalysis
)


@admin.register(VitalType)
class VitalTypeAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'category', 'unit', 
        'is_continuous', 'requires_multiple_values', 'is_active'
    ]
    list_filter = ['category', 'is_continuous', 'is_active']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'category', 'unit', 'description')
        }),
        ('Configuration', {
            'fields': ('is_continuous', 'requires_multiple_values', 'normal_range')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        }),
    )


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = [
        'device_name', 'patient', 'source_type', 'device_type',
        'is_active_status', 'last_sync_at', 'created_at'
    ]
    list_filter = ['source_type', 'device_type', 'is_active']
    search_fields = [
        'device_name', 'device_identifier', 
        'patient__user__first_name', 'patient__user__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'last_sync_at']
    
    fieldsets = (
        ('Patient', {
            'fields': ('patient',)
        }),
        ('Device Information', {
            'fields': (
                'source_type', 'device_type', 'device_name',
                'device_model', 'device_manufacturer', 'device_identifier'
            )
        }),
        ('Sync Configuration', {
            'fields': ('sync_frequency_minutes', 'last_sync_at', 'metadata')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def is_active_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">●</span> Active')
        return format_html('<span style="color: red;">●</span> Inactive')
    is_active_status.short_description = 'Status'


class VitalReadingEditInline(admin.TabularInline):
    model = VitalReadingEdit
    extra = 0
    readonly_fields = ['edited_by', 'edited_at']
    can_delete = False


@admin.register(VitalReading)
class VitalReadingAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'patient', 'vital_type', 'display_value_colored',
        'measured_at', 'anomaly_status', 'data_quality',
        'is_edited', 'is_deleted'
    ]
    list_filter = [
        'vital_type', 'is_anomaly', 'anomaly_severity',
        'data_quality', 'is_edited', 'is_deleted', 'measured_at'
    ]
    search_fields = [
        'patient__user__first_name', 'patient__user__last_name',
        'notes', 'session_id'
    ]
    readonly_fields = [
        'received_at', 'created_at', 'updated_at',
        'is_anomaly', 'anomaly_severity', 'anomaly_reason'
    ]
    date_hierarchy = 'measured_at'
    inlines = [VitalReadingEditInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('patient', 'vital_type', 'data_source', 'measured_at', 'received_at')
        }),
        ('Reading Values', {
            'fields': ('value', 'values', 'unit')
        }),
        ('Analysis', {
            'fields': (
                'is_anomaly', 'anomaly_severity', 'anomaly_reason',
                'data_quality', 'notes', 'tags'
            )
        }),
        ('Session Tracking', {
            'fields': ('session_id',)
        }),
        ('Audit Trail', {
            'fields': (
                'entered_by', 'is_edited', 'edited_at', 'edited_by',
                'is_deleted', 'deleted_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def display_value_colored(self, obj):
        value = obj.get_display_value()
        if obj.is_anomaly:
            if obj.anomaly_severity == 'CRITICAL':
                color = 'red'
            elif obj.anomaly_severity == 'HIGH':
                color = 'orange'
            else:
                color = 'yellow'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, value
            )
        return value
    display_value_colored.short_description = 'Value'
    
    def anomaly_status(self, obj):
        if obj.is_anomaly:
            colors = {
                'CRITICAL': 'red',
                'HIGH': 'orange',
                'ELEVATED': 'yellow',
                'NORMAL': 'green'
            }
            color = colors.get(obj.anomaly_severity, 'black')
            return format_html(
                '<span style="color: {};">● {}</span>',
                color, obj.anomaly_severity
            )
        return format_html('<span style="color: green;">● Normal</span>')
    anomaly_status.short_description = 'Anomaly Status'


@admin.register(VitalReadingEdit)
class VitalReadingEditAdmin(admin.ModelAdmin):
    list_display = [
        'vital_reading', 'edited_by', 'edited_at',
        'previous_value', 'new_value'
    ]
    list_filter = ['edited_at']
    search_fields = ['vital_reading__id', 'edit_reason', 'edited_by__username']
    readonly_fields = ['edited_at']


@admin.register(ContinuousVitalSession)
class ContinuousVitalSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id', 'patient', 'vital_type', 'started_at',
        'ended_at', 'status', 'total_readings', 'average_value'
    ]
    list_filter = ['status', 'vital_type', 'started_at']
    search_fields = ['session_id', 'patient__user__first_name']
    readonly_fields = [
        'created_at', 'updated_at', 'total_readings',
        'average_value', 'min_value', 'max_value'
    ]
    
    fieldsets = (
        ('Session Information', {
            'fields': ('patient', 'vital_type', 'data_source', 'session_id')
        }),
        ('Timing', {
            'fields': ('started_at', 'ended_at', 'status')
        }),
        ('Statistics', {
            'fields': (
                'total_readings', 'average_value', 
                'min_value', 'max_value'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(VitalTrendAnalysis)
class VitalTrendAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'vital_type', 'period_label',
        'trend_direction', 'trend_percentage',
        'reading_count', 'average_value', 'computed_at'
    ]
    list_filter = ['trend_direction', 'period_label', 'vital_type']
    search_fields = ['patient__user__first_name', 'patient__user__last_name']
    readonly_fields = ['computed_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('patient', 'vital_type', 'period_label')
        }),
        ('Time Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Statistics', {
            'fields': (
                'reading_count', 'average_value', 'min_value',
                'max_value', 'std_deviation'
            )
        }),
        ('Trend Analysis', {
            'fields': ('trend_direction', 'trend_percentage')
        }),
        ('Anomalies', {
            'fields': ('anomaly_count', 'critical_anomaly_count')
        }),
        ('Insights', {
            'fields': ('insights', 'computed_at')
        }),
    )
