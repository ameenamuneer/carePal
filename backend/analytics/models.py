from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from patients.models import PatientProfile
from users.models import User
from vitals.models import VitalType
from decimal import Decimal
import json


class HealthMetric(models.Model):
    """
    Pre-computed health metrics aggregations
    Computed by Celery tasks for performance
    """
    
    PERIOD_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='health_metrics'
    )
    
    # Period information
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Vital statistics (JSON structure for flexibility)
    vitals_summary = models.JSONField(
        default=dict,
        help_text="""
        {
            'BP': {
                'avg_systolic': 128, 'avg_diastolic': 82,
                'min_systolic': 115, 'max_systolic': 145,
                'readings_count': 42, 'trend': 'improving',
                'anomaly_count': 2
            },
            'HR': {...},
            'SPO2': {...}
        }
        """
    )
    
    # Medication statistics
    medication_adherence_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Percentage 0-100"
    )
    total_doses_scheduled = models.IntegerField(default=0)
    total_doses_taken = models.IntegerField(default=0)
    total_doses_missed = models.IntegerField(default=0)
    total_doses_skipped = models.IntegerField(default=0)
    critical_medication_misses = models.IntegerField(default=0)
    
    # Alert statistics
    total_alerts = models.IntegerField(default=0)
    info_alerts = models.IntegerField(default=0)
    warning_alerts = models.IntegerField(default=0)
    critical_alerts = models.IntegerField(default=0)
    emergency_alerts = models.IntegerField(default=0)
    avg_alert_response_time_minutes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    escalated_alerts_count = models.IntegerField(default=0)
    
    # Device statistics
    device_sync_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    total_device_syncs = models.IntegerField(default=0)
    failed_device_syncs = models.IntegerField(default=0)
    
    # Activity metrics (from devices)
    avg_daily_steps = models.IntegerField(null=True, blank=True)
    avg_sleep_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Overall health score (0-100)
    overall_health_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    health_score_category = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
            ('critical', 'Critical'),
        ],
        default='fair'
    )
    
    # Trend direction
    trend_direction = models.CharField(
        max_length=20,
        choices=[
            ('improving', 'Improving'),
            ('stable', 'Stable'),
            ('declining', 'Declining'),
            ('fluctuating', 'Fluctuating'),
        ],
        default='stable'
    )
    
    # Data quality
    data_completeness_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    
    # Metadata
    computed_at = models.DateTimeField(auto_now=True)
    computation_duration_seconds = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'health_metrics'
        ordering = ['-period_end']
        unique_together = ['patient', 'period_type', 'period_start']
        indexes = [
            models.Index(fields=['patient', 'period_type', '-period_end']),
            models.Index(fields=['period_end']),
        ]
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.period_type} - {self.period_start}"


class TrendAnalysis(models.Model):
    """
    Statistical trend analysis for correlations and patterns
    """
    
    ANALYSIS_TYPE_CHOICES = [
        ('correlation', 'Correlation Analysis'),
        ('regression', 'Regression Analysis'),
        ('pattern', 'Pattern Detection'),
        ('seasonal', 'Seasonal Analysis'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='trend_analyses'
    )
    
    # Analysis details
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPE_CHOICES)
    metric_1 = models.CharField(max_length=100, help_text="e.g., 'bp_systolic'")
    metric_2 = models.CharField(
        max_length=100,
        blank=True,
        help_text="For correlation analysis"
    )
    
    # Time range
    analysis_start_date = models.DateField()
    analysis_end_date = models.DateField()
    data_points_count = models.IntegerField(default=0)
    
    # Statistical results
    correlation_coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Pearson correlation: -1 to 1"
    )
    p_value = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Statistical significance"
    )
    r_squared = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Regression R²"
    )
    
    # Trend information
    trend_direction = models.CharField(max_length=20, blank=True)
    trend_strength = models.CharField(
        max_length=20,
        choices=[
            ('very_weak', 'Very Weak'),
            ('weak', 'Weak'),
            ('moderate', 'Moderate'),
            ('strong', 'Strong'),
            ('very_strong', 'Very Strong'),
        ],
        blank=True
    )
    
    # Results
    findings = models.JSONField(
        default=list,
        help_text="List of key findings"
    )
    statistical_summary = models.JSONField(
        default=dict,
        help_text="Detailed statistical results"
    )
    
    # Interpretation
    clinical_significance = models.TextField(blank=True)
    
    computed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'trend_analyses'
        ordering = ['-computed_at']
        indexes = [
            models.Index(fields=['patient', '-computed_at']),
        ]
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.analysis_type} - {self.metric_1}"


class RiskScore(models.Model):
    """
    Predictive risk assessment using ML models or rule-based scoring
    """
    
    RISK_TYPE_CHOICES = [
        ('hospitalization', 'Hospitalization Risk'),
        ('deterioration', 'Health Deterioration'),
        ('medication_nonadherence', 'Medication Non-Adherence'),
        ('falls', 'Fall Risk'),
        ('emergency', 'Emergency Event'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='risk_scores'
    )
    
    # Risk details
    risk_type = models.CharField(max_length=30, choices=RISK_TYPE_CHOICES)
    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Risk probability 0.0 to 1.0"
    )
    risk_category = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low Risk'),
            ('moderate', 'Moderate Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical Risk'),
        ]
    )
    
    # Contributing factors
    risk_factors = models.JSONField(
        default=list,
        help_text="List of factors contributing to risk"
    )
    risk_factor_weights = models.JSONField(
        default=dict,
        help_text="Weight of each factor"
    )
    
    # Model information
    model_type = models.CharField(
        max_length=50,
        choices=[
            ('rule_based', 'Rule-Based'),
            ('random_forest', 'Random Forest'),
            ('logistic_regression', 'Logistic Regression'),
            ('neural_network', 'Neural Network'),
        ],
        default='rule_based'
    )
    model_version = models.CharField(max_length=20, default='1.0.0')
    model_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=1.0,
        help_text="Model confidence in prediction"
    )
    
    # Recommendations
    recommended_actions = models.JSONField(
        default=list,
        help_text="Recommended interventions"
    )
    
    # Validity
    computed_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(
        help_text="Risk score validity period"
    )
    is_active = models.BooleanField(default=True)
    
    # Review
    requires_human_review = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_risk_scores'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'risk_scores'
        ordering = ['-computed_at']
        indexes = [
            models.Index(fields=['patient', 'risk_type', '-computed_at']),
            models.Index(fields=['is_active', 'risk_category']),
        ]
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.get_risk_type_display()} - {self.risk_category}"
    
    def save(self, *args, **kwargs):
        # Auto-determine category from score
        if self.risk_score >= 0.8:
            self.risk_category = 'critical'
        elif self.risk_score >= 0.6:
            self.risk_category = 'high'
        elif self.risk_score >= 0.4:
            self.risk_category = 'moderate'
        else:
            self.risk_category = 'low'
        
        # Set default validity (24 hours)
        if not self.valid_until:
            self.valid_until = timezone.now() + timezone.timedelta(hours=24)
        
        super().save(*args, **kwargs)


class InsightRecord(models.Model):
    """
    Record of generated insights (rule-based or AI-enhanced)
    For audit trail and validation
    """
    
    INSIGHT_TYPE_CHOICES = [
        ('rule_based', 'Rule-Based'),
        ('ai_enhanced', 'AI-Enhanced'),
        ('statistical', 'Statistical'),
        ('predictive', 'Predictive'),
    ]
    
    SOURCE_CHOICES = [
        ('metrics_engine', 'Metrics Engine'),
        ('trend_analyzer', 'Trend Analyzer'),
        ('gemini_api', 'Gemini API'),
        ('ml_model', 'ML Model'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='insight_records'
    )
    
    # Insight details
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPE_CHOICES)
    insight_text = models.TextField()
    insight_category = models.CharField(
        max_length=50,
        help_text="'vitals', 'medications', 'alerts', 'overall'"
    )
    
    # Source information
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    source_version = models.CharField(max_length=20, default='1.0.0')
    
    # For AI insights
    ai_model_name = models.CharField(max_length=100, blank=True)
    ai_model_version = models.CharField(max_length=50, blank=True)
    ai_temperature = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True
    )
    ai_prompt = models.TextField(blank=True)
    ai_raw_response = models.TextField(blank=True)
    
    # Validation
    validation_passed = models.BooleanField(default=True)
    validation_checks = models.JSONField(
        default=dict,
        help_text="Results of validation checks"
    )
    validation_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=1.0,
        help_text="Validation confidence 0-1"
    )
    
    # Confidence
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=1.0,
        help_text="Insight confidence 0-1"
    )
    
    # Source metrics
    source_metrics = models.JSONField(
        default=dict,
        help_text="Metrics used to generate insight"
    )
    
    # Usage tracking
    displayed_to_user = models.BooleanField(default=False)
    included_in_report = models.BooleanField(default=False)
    
    # Human review
    requires_review = models.BooleanField(default=False)
    human_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_insights'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    review_approved = models.BooleanField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'insight_records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'insight_type', '-created_at']),
            models.Index(fields=['validation_passed', 'requires_review']),
        ]
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.insight_type} - {self.insight_text[:50]}"


class HealthReport(models.Model):
    """
    Generated health reports in various formats
    """
    
    REPORT_TYPE_CHOICES = [
        ('daily_summary', 'Daily Summary'),
        ('weekly_progress', 'Weekly Progress'),
        ('monthly_comprehensive', 'Monthly Comprehensive'),
        ('doctor_visit', 'Doctor Visit Preparation'),
        ('incident', 'Incident Report'),
        ('compliance', 'Compliance Report'),
        ('custom', 'Custom Report'),
    ]
    
    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='health_reports'
    )
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_reports'
    )
    
    # Report details
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    report_title = models.CharField(max_length=200)
    report_description = models.TextField(blank=True)
    
    # Date range
    report_start_date = models.DateField()
    report_end_date = models.DateField()
    
    # Report content (structured data)
    report_data = models.JSONField(
        default=dict,
        help_text="Complete report data structure"
    )
    
    # Files
    pdf_file = models.FileField(
        upload_to='reports/pdf/%Y/%m/',
        null=True,
        blank=True
    )
    excel_file = models.FileField(
        upload_to='reports/excel/%Y/%m/',
        null=True,
        blank=True
    )
    
    # Sharing
    is_shared = models.BooleanField(default=False)
    shared_with = models.JSONField(
        default=list,
        help_text="List of user IDs who can access"
    )
    share_token = models.CharField(
        max_length=100,
        blank=True,
        unique=True,
        help_text="Token for secure sharing"
    )
    share_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generating')
    generation_error = models.TextField(blank=True)
    
    # Metadata
    template_version = models.CharField(max_length=20, default='1.0.0')
    ai_enhanced = models.BooleanField(default=False)
    data_quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Report validity expiration"
    )
    
    # Usage tracking
    view_count = models.IntegerField(default=0)
    download_count = models.IntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'health_reports'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['patient', '-generated_at']),
            models.Index(fields=['report_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.report_title} - {self.patient.user.get_full_name()}"


class ScheduledReport(models.Model):
    """
    Automated report scheduling
    """
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='scheduled_reports'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_scheduled_reports'
    )
    
    # Report configuration
    report_type = models.CharField(
        max_length=30,
        choices=HealthReport.REPORT_TYPE_CHOICES
    )
    report_name = models.CharField(max_length=200)
    
    # Schedule
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    day_of_week = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text="0=Monday for weekly reports"
    )
    day_of_month = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day of month for monthly reports"
    )
    time_of_day = models.TimeField(help_text="Time to generate report")
    
    # Recipients
    email_recipients = models.JSONField(
        default=list,
        help_text="List of email addresses"
    )
    
    # Configuration
    include_ai_insights = models.BooleanField(default=True)
    generate_pdf = models.BooleanField(default=True)
    generate_excel = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_generated_at = models.DateTimeField(null=True, blank=True)
    next_generation_at = models.DateTimeField()
    generation_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'scheduled_reports'
        ordering = ['next_generation_at']
    
    def __str__(self):
        return f"{self.report_name} - {self.get_frequency_display()}"


class ReportTemplate(models.Model):
    """
    Customizable report templates
    """
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(
        max_length=30,
        choices=HealthReport.REPORT_TYPE_CHOICES
    )
    description = models.TextField(blank=True)
    
    # Template configuration
    sections = models.JSONField(
        default=list,
        help_text="List of sections: ['vitals', 'medications', 'alerts', 'notes']"
    )
    section_order = models.JSONField(default=list)
    
    # Visualization preferences
    chart_types = models.JSONField(
        default=dict,
        help_text="Chart type per section: {'vitals': 'line', 'adherence': 'bar'}"
    )
    color_scheme = models.CharField(max_length=50, default='default')
    
    # Branding
    header_logo = models.ImageField(
        upload_to='report_templates/logos/',
        null=True,
        blank=True
    )
    footer_text = models.TextField(blank=True)
    
    # Settings
    include_raw_data = models.BooleanField(default=False)
    include_charts = models.BooleanField(default=True)
    include_insights = models.BooleanField(default=True)
    include_recommendations = models.BooleanField(default=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'report_templates'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class DashboardSnapshot(models.Model):
    """
    Cached dashboard data for performance
    """
    
    DASHBOARD_TYPE_CHOICES = [
        ('patient', 'Patient Dashboard'),
        ('family', 'Family Dashboard'),
        ('doctor', 'Doctor Dashboard'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='dashboard_snapshots'
    )
    
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPE_CHOICES)
    
    # Snapshot data
    snapshot_data = models.JSONField(
        default=dict,
        help_text="Complete dashboard data"
    )
    
    # Cache metadata
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_valid = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'dashboard_snapshots'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'dashboard_type', 'is_valid']),
        ]
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.dashboard_type}"
    
    def save(self, *args, **kwargs):
        # Set default expiration (5 minutes)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=5)
        
        # Check if expired
        if timezone.now() > self.expires_at:
            self.is_valid = False
        
        super().save(*args, **kwargs)
