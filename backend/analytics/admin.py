from django.contrib import admin
from django.utils.html import format_html
from .models import (
    HealthMetric, TrendAnalysis, RiskScore, InsightRecord,
    HealthReport, ScheduledReport, ReportTemplate, DashboardSnapshot
)


@admin.register(HealthMetric)
class HealthMetricAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'period_type', 'period_start', 'period_end',
        'health_score_badge', 'trend_direction', 'computed_at'
    ]
    list_filter = [
        'period_type', 'health_score_category', 'trend_direction',
        'period_start'
    ]
    search_fields = ['patient__user__first_name', 'patient__user__last_name']
    readonly_fields = ['computed_at', 'computation_duration_seconds']
    
    fieldsets = (
        ('Period', {
            'fields': ('patient', 'period_type', 'period_start', 'period_end')
        }),
        ('Vitals Summary', {
            'fields': ('vitals_summary',)
        }),
        ('Medication Metrics', {
            'fields': (
                'medication_adherence_rate', 'total_doses_scheduled',
                'total_doses_taken', 'total_doses_missed', 'total_doses_skipped',
                'critical_medication_misses'
            )
        }),
        ('Alert Metrics', {
            'fields': (
                'total_alerts', 'info_alerts', 'warning_alerts',
                'critical_alerts', 'emergency_alerts',
                'avg_alert_response_time_minutes', 'escalated_alerts_count'
            )
        }),
        ('Device Metrics', {
            'fields': (
                'device_sync_success_rate', 'total_device_syncs',
                'failed_device_syncs'
            )
        }),
        ('Activity Metrics', {
            'fields': ('avg_daily_steps', 'avg_sleep_hours')
        }),
        ('Overall Health', {
            'fields': (
                'overall_health_score', 'health_score_category',
                'trend_direction', 'data_completeness_percentage'
            )
        }),
        ('Computation', {
            'fields': ('computed_at', 'computation_duration_seconds')
        }),
    )
    
    def health_score_badge(self, obj):
        colors = {
            'excellent': 'green',
            'good': 'lightgreen',
            'fair': 'orange',
            'poor': 'red',
            'critical': 'darkred'
        }
        color = colors.get(obj.health_score_category, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.overall_health_score
        )
    health_score_badge.short_description = 'Health Score'


@admin.register(TrendAnalysis)
class TrendAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'analysis_type', 'metric_1', 'metric_2',
        'trend_strength', 'computed_at'
    ]
    list_filter = ['analysis_type', 'trend_strength', 'computed_at']
    search_fields = ['patient__user__first_name', 'metric_1', 'metric_2']
    readonly_fields = ['computed_at']


@admin.register(RiskScore)
class RiskScoreAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'risk_type', 'risk_category_badge',
        'risk_score', 'model_type', 'requires_human_review',
        'computed_at'
    ]
    list_filter = [
        'risk_type', 'risk_category', 'model_type',
        'requires_human_review', 'is_active'
    ]
    search_fields = ['patient__user__first_name', 'patient__user__last_name']
    readonly_fields = ['computed_at', 'risk_category']
    
    def risk_category_badge(self, obj):
        colors = {
            'low': 'green',
            'moderate': 'orange',
            'high': 'red',
            'critical': 'darkred'
        }
        color = colors.get(obj.risk_category, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_risk_category_display()
        )
    risk_category_badge.short_description = 'Risk Category'


@admin.register(InsightRecord)
class InsightRecordAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'insight_type', 'insight_category',
        'validation_badge', 'confidence_score',
        'requires_review', 'created_at'
    ]
    list_filter = [
        'insight_type', 'insight_category', 'validation_passed',
        'requires_review', 'human_reviewed'
    ]
    search_fields = ['patient__user__first_name', 'insight_text']
    readonly_fields = ['created_at']
    
    def validation_badge(self, obj):
        if obj.validation_passed:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Validated</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Failed</span>'
            )
    validation_badge.short_description = 'Validation'


@admin.register(HealthReport)
class HealthReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_title', 'patient', 'report_type',
        'status_badge', 'ai_enhanced', 'generated_at'
    ]
    list_filter = ['report_type', 'status', 'ai_enhanced', 'generated_at']
    search_fields = ['report_title', 'patient__user__first_name']
    readonly_fields = ['generated_at', 'view_count', 'download_count', 'last_accessed_at']
    
    def status_badge(self, obj):
        colors = {
            'generating': 'blue',
            'completed': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_name', 'patient', 'frequency',
        'is_active', 'next_generation_at', 'generation_count'
    ]
    list_filter = ['frequency', 'is_active', 'report_type']
    search_fields = ['report_name', 'patient__user__first_name']
    readonly_fields = ['last_generated_at', 'generation_count', 'created_at', 'updated_at']


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'report_type', 'is_default',
        'is_active', 'created_at'
    ]
    list_filter = ['report_type', 'is_default', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DashboardSnapshot)
class DashboardSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'dashboard_type', 'is_valid',
        'created_at', 'expires_at'
    ]
    list_filter = ['dashboard_type', 'is_valid', 'created_at']
    search_fields = ['patient__user__first_name']
    readonly_fields = ['created_at']
