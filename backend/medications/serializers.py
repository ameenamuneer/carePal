from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    Medication, MedicationAdherence,
    MedicationRefill, MedicationInteraction, MedicationAdherencePattern,
    MedicationEscalation
)


class MedicationListSerializer(serializers.ModelSerializer):
    """
    Simplified medication serializer for list views
    """
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    schedule_count = serializers.SerializerMethodField()
    next_dose_time = serializers.SerializerMethodField()
    adherence_rate_7d = serializers.SerializerMethodField()
    
    class Meta:
        model = Medication
        fields = [
            'id', 'patient', 'patient_name', 'medication_name',
            'dosage', 'form', 'route', 'frequency', 'status',
            'is_critical', 'quantity_remaining', 'quantity_prescribed',
            'start_date', 'end_date', 'schedule_count',
            'next_dose_time', 'adherence_rate_7d'
        ]
    
    def get_schedule_count(self, obj):
        """Number of daily doses derived from frequency."""
        from .schedule_utils import get_times_for_medication
        return len(get_times_for_medication(obj))

    def get_next_dose_time(self, obj):
        """Get next scheduled dose datetime"""
        next_adherence = MedicationAdherence.objects.filter(
            medication=obj,
            status='SCHEDULED',
            scheduled_datetime__gte=timezone.now()
        ).order_by('scheduled_datetime').first()
        
        if next_adherence:
            return next_adherence.scheduled_datetime.isoformat()
        return None
    
    def get_adherence_rate_7d(self, obj):
        """Calculate 7-day adherence rate"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=7)
        
        records = MedicationAdherence.objects.filter(
            medication=obj,
            scheduled_datetime__gte=start_date,
            scheduled_datetime__lte=end_date
        )
        
        total = records.count()
        if total == 0:
            return None
        
        taken = records.filter(status='TAKEN').count()
        return round((taken / total) * 100, 1)


class MedicationDetailSerializer(serializers.ModelSerializer):
    """
    Complete medication details with all related data
    """
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    dose_times = serializers.JSONField(read_only=True)
    needs_refill = serializers.BooleanField(read_only=True)
    days_until_empty = serializers.SerializerMethodField()
    adherence_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Medication
        fields = [
            'id', 'patient', 'patient_name', 'medication_name',
            'generic_name', 'dosage', 'form', 'route', 'frequency',
            'purpose', 'instructions', 'side_effects',
            'interactions', 'is_critical',
            'quantity_prescribed', 'quantity_remaining',
            'start_date', 'end_date', 'status', 'prescribed_by',
            'discontinued_by', 'discontinued_at', 'discontinuation_reason',
            'dose_times', 'needs_refill', 'days_until_empty',
            'adherence_summary', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'discontinued_at']
    
    def get_days_until_empty(self, obj):
        """Calculate days until medication runs out based on daily dose count from frequency."""
        from .schedule_utils import get_times_for_medication
        if not obj.quantity_remaining:
            return None
        daily_doses = len(get_times_for_medication(obj))
        if daily_doses == 0:
            return None
        return int(obj.quantity_remaining / daily_doses)
    
    def get_adherence_summary(self, obj):
        """Get comprehensive adherence summary"""
        end_date = timezone.now()
        
        # 7-day summary
        start_7d = end_date - timedelta(days=7)
        records_7d = MedicationAdherence.objects.filter(
            medication=obj,
            scheduled_datetime__gte=start_7d,
            scheduled_datetime__lte=end_date
        )
        
        # 30-day summary
        start_30d = end_date - timedelta(days=30)
        records_30d = MedicationAdherence.objects.filter(
            medication=obj,
            scheduled_datetime__gte=start_30d,
            scheduled_datetime__lte=end_date
        )
        
        def calculate_stats(records):
            total = records.count()
            if total == 0:
                return None
            
            taken = records.filter(status='TAKEN').count()
            missed = records.filter(status='MISSED').count()
            skipped = records.filter(status='SKIPPED').count()
            
            return {
                'total': total,
                'taken': taken,
                'missed': missed,
                'skipped': skipped,
                'rate': round((taken / total) * 100, 1)
            }
        
        return {
            'last_7_days': calculate_stats(records_7d),
            'last_30_days': calculate_stats(records_30d)
        }


class MedicationCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating medications.
    dose_times is auto-set from frequency on create; can be passed explicitly to override.
    """
    class Meta:
        model = Medication
        fields = [
            'patient', 'medication_name', 'generic_name', 'dosage',
            'form', 'route', 'frequency', 'purpose', 'instructions',
            'side_effects', 'interactions',
            'is_critical', 'quantity_prescribed',
            'quantity_remaining', 'start_date',
            'end_date', 'prescribed_by', 'dose_times',
        ]
    
    def create(self, validated_data):
        """Create medication. Auto-sets dose_times from frequency if not provided."""
        from .schedule_utils import default_dose_times_for_frequency
        validated_data.pop('schedules', [])   # unused
        # Auto-populate dose_times so patient-preferred times are stored on the model
        if not validated_data.get('dose_times'):
            validated_data['dose_times'] = default_dose_times_for_frequency(
                validated_data.get('frequency', 'ONCE_DAILY')
            )
        medication = Medication.objects.create(**validated_data)
        return medication
    
    def update(self, instance, validated_data):
        """Update medication fields. Schedule times derive from frequency — no MedicationSchedule rows touched."""
        validated_data.pop('schedules', None)  # unused
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class MedicationAdherenceDetailSerializer(serializers.ModelSerializer):
    """
    Detailed adherence record with full medication info
    """
    medication_name = serializers.CharField(source='medication.medication_name', read_only=True)
    medication_dosage = serializers.CharField(source='medication.dosage', read_only=True)
    medication_form = serializers.CharField(source='medication.form', read_only=True)
    medication_is_critical = serializers.BooleanField(source='medication.is_critical', read_only=True)
    
    is_overdue = serializers.BooleanField(read_only=True)
    delay_minutes = serializers.IntegerField(read_only=True)
    scheduled_datetime_display = serializers.SerializerMethodField()
    actual_datetime_display = serializers.SerializerMethodField()
    
    class Meta:
        model = MedicationAdherence
        fields = [
            'id', 'medication', 'medication_name', 'medication_dosage',
            'medication_form', 'medication_is_critical',
            'scheduled_date', 'scheduled_time', 'scheduled_datetime',
            'scheduled_datetime_display', 'actual_datetime', 'actual_datetime_display',
            'status', 'confirmed_by_patient', 'confirmation_method',
            'skip_reason', 'miss_reason', 'notes', 'side_effects_reported',
            'reminder_sent_at', 'reminder_count', 'is_overdue', 'delay_minutes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_scheduled_datetime_display(self, obj):
        """Format scheduled datetime"""
        if obj.scheduled_datetime:
            return obj.scheduled_datetime.strftime('%I:%M %p')
        return None
    
    def get_actual_datetime_display(self, obj):
        """Format actual datetime"""
        if obj.actual_datetime:
            return obj.actual_datetime.strftime('%I:%M %p')
        return None


class TodaysMedicationScheduleSerializer(serializers.Serializer):
    """
    Today's medication schedule with all necessary details for frontend
    """
    adherence_id = serializers.IntegerField()
    medication_id = serializers.IntegerField()
    medication_name = serializers.CharField()
    dosage = serializers.CharField()
    form = serializers.CharField()
    instructions = serializers.CharField(allow_blank=True)
    
    scheduled_time = serializers.TimeField()
    scheduled_time_display = serializers.SerializerMethodField()
    time_label = serializers.CharField()
    with_food = serializers.BooleanField()
    special_instructions = serializers.CharField(allow_blank=True)
    
    is_critical = serializers.BooleanField()
    status = serializers.CharField()
    actual_datetime = serializers.DateTimeField(allow_null=True)
    notes = serializers.CharField(allow_blank=True)
    is_overdue = serializers.BooleanField()
    
    # Additional helper fields
    can_take = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()
    status_icon = serializers.SerializerMethodField()
    
    def get_scheduled_time_display(self, obj):
        """Format time in 12-hour format"""
        time = obj.get('scheduled_time')
        if time:
            dt = datetime.combine(datetime.today(), time)
            return dt.strftime('%I:%M %p')
        return None
    
    def get_can_take(self, obj):
        """Determine if medication can be marked as taken"""
        status = obj.get('status')
        return status == 'SCHEDULED'
    
    def get_status_color(self, obj):
        """Get color for status badge"""
        status = obj.get('status')
        color_map = {
            'TAKEN': '#10B981',      # Green
            'MISSED': '#EF4444',     # Red
            'SKIPPED': '#6B7280',    # Gray
            'SCHEDULED': '#F59E0B'   # Amber
        }
        return color_map.get(status, '#6B7280')
    
    def get_status_icon(self, obj):
        """Get icon name for status"""
        status = obj.get('status')
        icon_map = {
            'TAKEN': 'check_circle',
            'MISSED': 'cancel',
            'SKIPPED': 'block',
            'SCHEDULED': 'schedule'
        }
        return icon_map.get(status, 'help')


class AdherenceRateSerializer(serializers.Serializer):
    """
    Adherence rate calculation response
    """
    period_days = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    total_scheduled = serializers.IntegerField()
    total_taken = serializers.IntegerField()
    total_missed = serializers.IntegerField()
    total_skipped = serializers.IntegerField()
    
    adherence_rate = serializers.FloatField()
    completion_rate = serializers.FloatField()
    
    # Trend data
    daily_breakdown = serializers.ListField(child=serializers.DictField(), required=False)


# ==========================================
# Legacy/Auxiliary Serializers (Preserved)
# ==========================================

class MedicationEscalationSerializer(serializers.ModelSerializer):
    """Serializer for escalation records"""
    
    medication_name = serializers.CharField(source='medication.medication_name', read_only=True)
    
    class Meta:
        model = MedicationEscalation
        fields = [
            'id', 'adherence_record', 'medication', 'medication_name',
            'action_taken', 'action_details', 'escalation_reason',
            'consecutive_misses', 'successful', 'response_received',
            'response_details', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class MedicationInteractionSerializer(serializers.ModelSerializer):
    """Serializer for drug interactions"""
    
    medication_1_name = serializers.CharField(source='medication_1.medication_name', read_only=True)
    medication_2_name = serializers.CharField(source='medication_2.medication_name', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)
    
    class Meta:
        model = MedicationInteraction
        fields = [
            'id', 'medication_1', 'medication_1_name', 'medication_2',
            'medication_2_name', 'severity', 'description', 'clinical_effects',
            'management', 'acknowledged_by', 'acknowledged_by_name',
            'acknowledged_at', 'override_reason', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class MedicationRefillSerializer(serializers.ModelSerializer):
    """Serializer for refill requests"""
    
    medication_name = serializers.CharField(source='medication.medication_name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    
    class Meta:
        model = MedicationRefill
        fields = [
            'id', 'medication', 'medication_name', 'requested_date',
            'requested_by', 'requested_by_name', 'quantity',
            'pharmacy_name', 'pharmacy_phone', 'status',
            'approved_by', 'approved_at', 'filled_date', 'pickup_date',
            'notes', 'cancellation_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'requested_date', 'created_at', 'updated_at']


class MedicationAdherencePatternSerializer(serializers.ModelSerializer):
    """Serializer for adherence patterns"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    medication_name = serializers.CharField(source='medication.medication_name', read_only=True, allow_null=True)
    
    class Meta:
        model = MedicationAdherencePattern
        fields = [
            'id', 'patient', 'patient_name', 'medication', 'medication_name',
            'period_start', 'period_end', 'period_label',
            'total_scheduled', 'total_taken', 'total_missed', 'total_skipped',
            'adherence_rate', 'most_missed_time', 'most_missed_day',
            'consecutive_misses_max', 'average_delay_minutes',
            'insights', 'recommendations', 'computed_at'
        ]
