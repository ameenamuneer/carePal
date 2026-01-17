from rest_framework import serializers
from .models import (
    HealthMetric, TrendAnalysis, RiskScore, InsightRecord,
    HealthReport, ScheduledReport, ReportTemplate, DashboardSnapshot
)


class HealthMetricSerializer(serializers.ModelSerializer):
    """Serializer for health metrics"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = HealthMetric
        fields = [
            'id', 'patient', 'patient_name', 'period_type', 'period_start',
            'period_end', 'vitals_summary', 'medication_adherence_rate',
            'total_doses_scheduled', 'total_doses_taken', 'total_doses_missed',
            'total_doses_skipped', 'critical_medication_misses', 'total_alerts',
            'info_alerts', 'warning_alerts', 'critical_alerts', 'emergency_alerts',
            'avg_alert_response_time_minutes', 'escalated_alerts_count',
            'device_sync_success_rate', 'total_device_syncs', 'failed_device_syncs',
            'avg_daily_steps', 'avg_sleep_hours', 'overall_health_score',
            'health_score_category', 'trend_direction', 'data_completeness_percentage',
            'computed_at', 'computation_duration_seconds'
        ]
        read_only_fields = ['id', 'computed_at']


class TrendAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for trend analysis"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = TrendAnalysis
        fields = [
            'id', 'patient', 'patient_name', 'analysis_type', 'metric_1',
            'metric_2', 'analysis_start_date', 'analysis_end_date',
            'data_points_count', 'correlation_coefficient', 'p_value',
            'r_squared', 'trend_direction', 'trend_strength', 'findings',
            'statistical_summary', 'clinical_significance', 'computed_at'
        ]
        read_only_fields = ['id', 'computed_at']


class RiskScoreSerializer(serializers.ModelSerializer):
    """Serializer for risk scores"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
    
    class Meta:
        model = RiskScore
        fields = [
            'id', 'patient', 'patient_name', 'risk_type', 'risk_score',
            'risk_category', 'risk_factors', 'risk_factor_weights',
            'model_type', 'model_version', 'model_confidence',
            'recommended_actions', 'computed_at', 'valid_until',
            'is_active', 'requires_human_review', 'reviewed_by',
            'reviewed_by_name', 'reviewed_at', 'review_notes'
        ]
        read_only_fields = ['id', 'computed_at', 'risk_category']


class InsightRecordSerializer(serializers.ModelSerializer):
    """Serializer for insight records"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
    
    class Meta:
        model = InsightRecord
        fields = [
            'id', 'patient', 'patient_name', 'insight_type', 'insight_text',
            'insight_category', 'source', 'source_version', 'ai_model_name',
            'ai_model_version', 'ai_temperature', 'validation_passed',
            'validation_checks', 'validation_score', 'confidence_score',
            'source_metrics', 'displayed_to_user', 'included_in_report',
            'requires_review', 'human_reviewed', 'reviewed_by',
            'reviewed_by_name', 'reviewed_at', 'review_notes',
            'review_approved', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class HealthReportSerializer(serializers.ModelSerializer):
    """Serializer for health reports"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)
    
    class Meta:
        model = HealthReport
        fields = [
            'id', 'patient', 'patient_name', 'generated_by', 'generated_by_name',
            'report_type', 'report_title', 'report_description',
            'report_start_date', 'report_end_date', 'report_data',
            'pdf_file', 'excel_file', 'is_shared', 'shared_with',
            'share_token', 'share_expires_at', 'status', 'generation_error',
            'template_version', 'ai_enhanced', 'data_quality_score',
            'generated_at', 'expires_at', 'view_count', 'download_count',
            'last_accessed_at'
        ]
        read_only_fields = [
            'id', 'generated_at', 'view_count', 'download_count',
            'last_accessed_at'
        ]


class HealthReportListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing reports"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = HealthReport
        fields = [
            'id', 'patient_name', 'report_type', 'report_title',
            'report_start_date', 'report_end_date', 'status',
            'ai_enhanced', 'generated_at'
        ]


class GenerateReportSerializer(serializers.Serializer):
    """Serializer for report generation request"""
    
    patient_id = serializers.IntegerField(required=True)
    report_type = serializers.ChoiceField(
        choices=HealthReport.REPORT_TYPE_CHOICES,
        required=True
    )
    report_title = serializers.CharField(max_length=200, required=False)
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    include_ai_insights = serializers.BooleanField(default=True)
    generate_pdf = serializers.BooleanField(default=True)
    generate_excel = serializers.BooleanField(default=False)
    template_id = serializers.IntegerField(required=False, allow_null=True)


class ScheduledReportSerializer(serializers.ModelSerializer):
    """Serializer for scheduled reports"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = ScheduledReport
        fields = [
            'id', 'patient', 'patient_name', 'created_by', 'created_by_name',
            'report_type', 'report_name', 'frequency', 'day_of_week',
            'day_of_month', 'time_of_day', 'email_recipients',
            'include_ai_insights', 'generate_pdf', 'generate_excel',
            'is_active', 'last_generated_at', 'next_generation_at',
            'generation_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'last_generated_at', 'generation_count',
            'created_at', 'updated_at'
        ]


class ReportTemplateSerializer(serializers.ModelSerializer):
    """Serializer for report templates"""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = ReportTemplate
        fields = [
            'id', 'name', 'report_type', 'description', 'sections',
            'section_order', 'chart_types', 'color_scheme', 'header_logo',
            'footer_text', 'include_raw_data', 'include_charts',
            'include_insights', 'include_recommendations', 'is_default',
            'is_active', 'created_by', 'created_by_name', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DashboardSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for dashboard snapshots"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = DashboardSnapshot
        fields = [
            'id', 'patient', 'patient_name', 'dashboard_type',
            'snapshot_data', 'created_at', 'expires_at', 'is_valid'
        ]
        read_only_fields = ['id', 'created_at', 'expires_at', 'is_valid']


class PatientDashboardSerializer(serializers.Serializer):
    """Serializer for patient dashboard data"""
    
    patient_id = serializers.IntegerField()
    patient_name = serializers.CharField()
    health_score = serializers.DictField()
    vitals_summary = serializers.DictField()
    medication_adherence = serializers.DictField()
    alerts = serializers.DictField()
    risk_assessment = serializers.DictField()
    insights = serializers.ListField()
    recommendations = serializers.ListField()
    data_completeness = serializers.DecimalField(max_digits=5, decimal_places=2)
    last_updated = serializers.DateTimeField()


class FamilyDashboardSerializer(serializers.Serializer):
    """Serializer for family dashboard data"""
    
    patient_id = serializers.IntegerField()
    patient_name = serializers.CharField()
    patient_status = serializers.CharField()
    health_score = serializers.IntegerField()
    recent_vitals = serializers.DictField()
    medication_adherence_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    active_alerts = serializers.ListField()
    critical_alerts_count = serializers.IntegerField()
    recent_insights = serializers.ListField()
    upcoming_appointments = serializers.ListField()
    last_updated = serializers.DateTimeField()


class ComputeMetricsSerializer(serializers.Serializer):
    """Serializer for manual metrics computation"""
    
    patient_id = serializers.IntegerField(required=True)
    period_type = serializers.ChoiceField(
        choices=HealthMetric.PERIOD_TYPE_CHOICES,
        required=True
    )
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
