from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from patients.models import PatientProfile
from users.models import User
import json

class VitalType(models.Model):
    """
    Catalog of vital sign types supported by the system
    """
    
    MEASUREMENT_UNIT_CHOICES = [
        ('mmHg', 'Millimeters of Mercury'),
        ('bpm', 'Beats per Minute'),
        ('percent', 'Percentage'),
        ('celsius', 'Degrees Celsius'),
        ('fahrenheit', 'Degrees Fahrenheit'),
        ('mg_dl', 'Milligrams per Deciliter'),
        ('mmol_l', 'Millimoles per Liter'),
        ('breaths_min', 'Breaths per Minute'),
        ('kg', 'Kilograms'),
        ('lbs', 'Pounds'),
        ('steps', 'Steps'),
        ('hours', 'Hours'),
    ]
    
    VITAL_CATEGORY_CHOICES = [
        ('CARDIOVASCULAR', 'Cardiovascular'),
        ('RESPIRATORY', 'Respiratory'),
        ('METABOLIC', 'Metabolic'),
        ('PHYSICAL', 'Physical Activity'),
        ('BODY', 'Body Measurements'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True, help_text="Short code like BP, HR, SPO2")
    category = models.CharField(max_length=20, choices=VITAL_CATEGORY_CHOICES)
    unit = models.CharField(max_length=20, choices=MEASUREMENT_UNIT_CHOICES)
    description = models.TextField(blank=True)
    
    # Normal ranges (can be age/gender specific, stored as JSON)
    normal_range = models.JSONField(
        default=dict,
        help_text="Normal ranges: {'min': 60, 'max': 100, 'critical_low': 50, 'critical_high': 120}"
    )
    
    # Configuration
    is_continuous = models.BooleanField(
        default=False,
        help_text="True for continuous monitoring (heart rate from watch), False for discrete (BP reading)"
    )
    requires_multiple_values = models.BooleanField(
        default=False,
        help_text="True for BP (systolic/diastolic), False for single value vitals"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'vital_types'
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class DataSource(models.Model):
    """
    Track different data sources for vitals
    """
    
    SOURCE_TYPE_CHOICES = [
        ('BLUETOOTH_DEVICE', 'Bluetooth Medical Device'),
        ('CLOUD_API', 'Cloud API (Fitbit/Apple Health)'),
        ('MANUAL_ENTRY', 'Manual Entry'),
        ('HOSPITAL_SYSTEM', 'Hospital System Integration'),
        ('CAREPAL_DEVICE', 'CarePAL Device'),
    ]
    
    DEVICE_TYPE_CHOICES = [
        ('BP_MONITOR', 'Blood Pressure Monitor'),
        ('PULSE_OXIMETER', 'Pulse Oximeter'),
        ('THERMOMETER', 'Thermometer'),
        ('GLUCOMETER', 'Glucose Meter'),
        ('WEIGHT_SCALE', 'Weight Scale'),
        ('HEART_RATE_MONITOR', 'Heart Rate Monitor'),
        ('SMARTWATCH', 'Smartwatch'),
        ('FITNESS_TRACKER', 'Fitness Tracker'),
        ('CLINICAL_MONITOR', 'Clinical Patient Monitor'),
        ('VENTILATOR', 'Ventilator'),
        ('MANUAL', 'Manual Entry'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile, 
        on_delete=models.CASCADE, 
        related_name='data_sources'
    )
    
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    device_type = models.CharField(max_length=30, choices=DEVICE_TYPE_CHOICES)
    
    # Device Identification
    device_name = models.CharField(max_length=200)
    device_model = models.CharField(max_length=100, blank=True)
    device_manufacturer = models.CharField(max_length=100, blank=True)
    device_identifier = models.CharField(
        max_length=200, 
        blank=True,
        help_text="MAC address, serial number, or API identifier"
    )
    
    # Connection Info
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_frequency_minutes = models.IntegerField(
        null=True, 
        blank=True,
        help_text="For cloud APIs, how often to sync"
    )
    
    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional device-specific configuration"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'data_sources'
        ordering = ['-created_at']
        unique_together = ['patient', 'device_identifier']
    
    def __str__(self):
        return f"{self.device_name} - {self.patient.user.get_full_name()}"


class VitalReading(models.Model):
    """
    Main table for storing vital sign readings
    Supports both discrete and continuous data
    """
    
    SEVERITY_CHOICES = [
        ('NORMAL', 'Normal'),
        ('ELEVATED', 'Elevated'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='vital_readings'
    )
    vital_type = models.ForeignKey(
        VitalType,
        on_delete=models.PROTECT,
        related_name='readings'
    )
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='readings'
    )
    
    # Timestamps
    measured_at = models.DateTimeField(
        help_text="When the reading was actually taken"
    )
    received_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the system received this reading"
    )
    
    # Values - supports multiple formats
    # For single-value vitals (heart rate, SpO2, temperature)
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # For multi-value vitals (blood pressure: systolic/diastolic)
    values = models.JSONField(
        default=dict,
        blank=True,
        help_text="{'systolic': 120, 'diastolic': 80} or {'value': 98.6}"
    )
    
    # Unit of measurement
    unit = models.CharField(max_length=20)
    
    # Analysis
    is_anomaly = models.BooleanField(default=False)
    anomaly_severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='NORMAL'
    )
    anomaly_reason = models.TextField(
        blank=True,
        help_text="Why this was flagged as anomaly"
    )
    
    # Quality indicators
    data_quality = models.CharField(
        max_length=20,
        choices=[
            ('EXCELLENT', 'Excellent'),
            ('GOOD', 'Good'),
            ('FAIR', 'Fair'),
            ('POOR', 'Poor'),
        ],
        default='GOOD'
    )
    
    # Additional context
    notes = models.TextField(blank=True)
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="['fasting', 'post_meal', 'pre_medication', 'post_exercise']"
    )
    
    # Session tracking (for continuous monitoring)
    session_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Links continuous readings to a monitoring session"
    )
    
    # Manual entry tracking
    entered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entered_vitals'
    )
    
    # Edit tracking
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='edited_vitals'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vital_readings'
        ordering = ['-measured_at']
        indexes = [
            models.Index(fields=['patient', 'vital_type', '-measured_at']),
            models.Index(fields=['patient', '-measured_at']),
            models.Index(fields=['is_anomaly', 'anomaly_severity']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.vital_type.name}: {self.get_display_value()} - {self.patient.user.get_full_name()}"
    
    def get_display_value(self):
        """Return formatted display value"""
        if self.vital_type.requires_multiple_values and self.values:
            # Blood Pressure: 120/80 mmHg
            if 'systolic' in self.values and 'diastolic' in self.values:
                return f"{self.values['systolic']}/{self.values['diastolic']} {self.unit}"
        elif self.value is not None:
            return f"{self.value} {self.unit}"
        return "N/A"
    
    def check_anomaly(self):
        """Check if reading is anomalous based on normal ranges"""
        if not self.vital_type.normal_range:
            return False
        
        normal_range = self.vital_type.normal_range
        
        # For single value vitals
        if self.value is not None:
            val = float(self.value)
            
            if 'critical_low' in normal_range and val < normal_range['critical_low']:
                self.is_anomaly = True
                self.anomaly_severity = 'CRITICAL'
                self.anomaly_reason = f"Value {val} below critical threshold {normal_range['critical_low']}"
                return True
            
            if 'critical_high' in normal_range and val > normal_range['critical_high']:
                self.is_anomaly = True
                self.anomaly_severity = 'CRITICAL'
                self.anomaly_reason = f"Value {val} above critical threshold {normal_range['critical_high']}"
                return True
            
            if 'min' in normal_range and val < normal_range['min']:
                self.is_anomaly = True
                self.anomaly_severity = 'ELEVATED'
                self.anomaly_reason = f"Value {val} below normal minimum {normal_range['min']}"
                return True
            
            if 'max' in normal_range and val > normal_range['max']:
                self.is_anomaly = True
                self.anomaly_severity = 'HIGH'
                self.anomaly_reason = f"Value {val} above normal maximum {normal_range['max']}"
                return True
        
        # For multi-value vitals (e.g., blood pressure)
        if self.values and 'systolic' in self.values:
            systolic = float(self.values['systolic'])
            diastolic = float(self.values.get('diastolic', 0))
            
            if systolic >= 180 or diastolic >= 120:
                self.is_anomaly = True
                self.anomaly_severity = 'CRITICAL'
                self.anomaly_reason = "Hypertensive crisis"
                return True
            elif systolic >= 140 or diastolic >= 90:
                self.is_anomaly = True
                self.anomaly_severity = 'HIGH'
                self.anomaly_reason = "High blood pressure"
                return True
        
        return False
    
    def save(self, *args, **kwargs):
        # Auto-check for anomalies
        self.check_anomaly()
        super().save(*args, **kwargs)


class VitalReadingEdit(models.Model):
    """
    Audit trail for vital reading edits
    """
    vital_reading = models.ForeignKey(
        VitalReading,
        on_delete=models.CASCADE,
        related_name='edit_history'
    )
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Store previous values
    previous_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    previous_values = models.JSONField(default=dict, blank=True)
    previous_notes = models.TextField(blank=True)
    
    # Store new values
    new_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    new_notes = models.TextField(blank=True)
    
    # Edit metadata
    edit_reason = models.TextField()
    edited_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'vital_reading_edits'
        ordering = ['-edited_at']
    
    def __str__(self):
        return f"Edit by {self.edited_by} at {self.edited_at}"


class ContinuousVitalSession(models.Model):
    """
    Track continuous monitoring sessions (e.g., heart rate from smartwatch)
    """
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='continuous_sessions'
    )
    vital_type = models.ForeignKey(VitalType, on_delete=models.PROTECT)
    data_source = models.ForeignKey(DataSource, on_delete=models.SET_NULL, null=True)
    
    session_id = models.CharField(max_length=100, unique=True)
    
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Statistics
    total_readings = models.IntegerField(default=0)
    average_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'continuous_vital_sessions'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.vital_type.name} session - {self.patient.user.get_full_name()}"


class VitalTrendAnalysis(models.Model):
    """
    Store computed trend analysis for vitals
    Computed periodically by background tasks
    """
    
    TREND_DIRECTION_CHOICES = [
        ('IMPROVING', 'Improving'),
        ('STABLE', 'Stable'),
        ('DECLINING', 'Declining'),
        ('FLUCTUATING', 'Fluctuating'),
    ]
    
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='vital_trends')
    vital_type = models.ForeignKey(VitalType, on_delete=models.PROTECT)
    
    # Time period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    period_label = models.CharField(
        max_length=50,
        help_text="'last_24h', 'last_7days', 'last_30days'"
    )
    
    # Statistics
    reading_count = models.IntegerField(default=0)
    average_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_value = models.DecimalField(max_digits=10, decimal_places=2)
    std_deviation = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Trend analysis
    trend_direction = models.CharField(max_length=20, choices=TREND_DIRECTION_CHOICES)
    trend_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage change compared to previous period"
    )
    
    # Anomalies in this period
    anomaly_count = models.IntegerField(default=0)
    critical_anomaly_count = models.IntegerField(default=0)
    
    # Insights
    insights = models.JSONField(
        default=list,
        help_text="AI-generated insights about the trend"
    )
    
    computed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vital_trend_analysis'
        ordering = ['-period_end']
        unique_together = ['patient', 'vital_type', 'period_label', 'period_start']
    
    def __str__(self):
        return f"{self.vital_type.name} trend - {self.period_label}"
