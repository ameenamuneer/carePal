from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    AlertType, Alert, AlertDelivery, AlertRule,
    NotificationPreference, AlertEscalation, AlertTemplate,
    AlertStatistics
)


@admin.register(AlertType)
class AlertTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'default_severity', 'is_active')
    list_filter = ('category', 'default_severity', 'is_active')
    search_fields = ('name', 'code', 'message_template')


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'patient_name', 'severity_badge', 'status_badge', 'created_at')
    list_filter = ('severity', 'status', 'alert_type__category', 'created_at')
    search_fields = ('title', 'message', 'patient__user__first_name', 'patient__user__last_name')
    readonly_fields = ('created_at', 'sent_at', 'delivered_at', 'acknowledged_at', 'resolved_at', 'escalated_at')
    
    actions = ['acknowledge_alerts', 'resolve_alerts']
    
    def patient_name(self, obj):
        return obj.patient.user.get_full_name()
    patient_name.short_description = 'Patient'
    
    def severity_badge(self, obj):
        colors = {
            'INFO': 'blue',
            'WARNING': 'orange',
            'CRITICAL': 'red',
            'EMERGENCY': 'darkred',
        }
        color = colors.get(obj.severity, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 10px;">{}</span>',
            color,
            obj.severity
        )
    severity_badge.short_description = 'Severity'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'gray',
            'SENT': 'lightblue',
            'DELIVERED': 'blue',
            'ACKNOWLEDGED': 'orange',
            'RESOLVED': 'green',
            'ESCALATED': 'red',
            'FAILED': 'darkred',
            'EXPIRED': 'lightgray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 10px;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'

    def acknowledge_alerts(self, request, queryset):
        count = queryset.update(
            status='ACKNOWLEDGED',
            acknowledged_at=timezone.now(),
            acknowledged_by=request.user
        )
        self.message_user(request, f"{count} alerts acknowledged.")
    acknowledge_alerts.short_description = "Acknowledge selected alerts"

    def resolve_alerts(self, request, queryset):
        count = queryset.update(
            status='RESOLVED',
            resolved_at=timezone.now(),
            resolved_by=request.user
        )
        self.message_user(request, f"{count} alerts resolved.")
    resolve_alerts.short_description = "Resolve selected alerts"


@admin.register(AlertDelivery)
class AlertDeliveryAdmin(admin.ModelAdmin):
    list_display = ('alert', 'recipient_name', 'channel', 'status', 'created_at')
    list_filter = ('channel', 'status', 'created_at')
    search_fields = ('recipient__first_name', 'recipient__last_name', 'recipient_address')
    
    def recipient_name(self, obj):
        return obj.recipient.get_full_name()
    recipient_name.short_description = 'Recipient'


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'patient_name', 'alert_type', 'rule_type', 'is_active')
    list_filter = ('rule_type', 'is_active', 'alert_type')
    search_fields = ('name', 'patient__user__first_name', 'patient__user__last_name')
    
    def patient_name(self, obj):
        return obj.patient.user.get_full_name()
    patient_name.short_description = 'Patient'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'enable_push', 'enable_sms', 'enable_email')
    search_fields = ('user__first_name', 'user__last_name', 'user__email')


@admin.register(AlertEscalation)
class AlertEscalationAdmin(admin.ModelAdmin):
    list_display = ('alert', 'escalation_type', 'escalation_level', 'escalated_at')
    list_filter = ('escalation_type', 'escalation_level', 'escalated_at')


@admin.register(AlertTemplate)
class AlertTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'alert_type', 'language', 'is_active')
    list_filter = ('language', 'is_active', 'alert_type')
    search_fields = ('name', 'subject_template', 'message_template')


@admin.register(AlertStatistics)
class AlertStatisticsAdmin(admin.ModelAdmin):
    list_display = ('patient', 'period_label', 'period_end', 'total_alerts', 'critical_count')
    list_filter = ('period_label', 'period_end')
