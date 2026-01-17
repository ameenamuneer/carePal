from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    Medication, MedicationSchedule, MedicationAdherence,
    MedicationEscalation, MedicationInteraction, MedicationRefill,
    MedicationAdherencePattern
)


class MedicationScheduleSerializer(serializers.ModelSerializer):
    """Serializer for medication schedules"""
    
    should_remind_today = serializers.ReadOnlyField()
    
    class Meta:
        model = MedicationSchedule
        fields = [
            'id', 'time_of_day', 'time_label', 'days_of_week',
            'with_food', 'on_empty_stomach', 'reminder_enabled',
            'reminder_advance_minutes', 'is_active', 'should_remind_today',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class MedicationSerializer(serializers.ModelSerializer):
    """Full medication serializer"""
    
    schedules = MedicationScheduleSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    is_active = serializers.ReadOnlyField()
    needs_refill = serializers.ReadOnlyField()
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = Medication
        fields = [
            'id', 'patient', 'patient_name', 'medication_name', 'generic_name',
            'brand_name', 'dosage', 'form', 'route', 'frequency', 'times_per_day',
            'start_date', 'end_date', 'duration_days', 'instructions',
            'special_instructions', 'prescribed_by', 'prescription_number',
            'prescribed_date', 'quantity_prescribed', 'quantity_remaining',
            'refills_allowed', 'refills_remaining', 'status',
            'discontinuation_reason', 'discontinued_by', 'discontinued_at',
            'side_effects', 'interactions', 'purpose', 'is_critical',
            'schedules', 'is_active', 'needs_refill', 'days_remaining',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_days_remaining(self, obj):
        """Calculate days remaining until end date"""
        if obj.end_date:
            today = timezone.now().date()
            if obj.end_date > today:
                return (obj.end_date - today).days
        return None


class MedicationCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating medications"""
    
    schedules = MedicationScheduleSerializer(many=True, required=False)
    
    class Meta:
        model = Medication
        fields = [
            'patient', 'medication_name', 'generic_name', 'brand_name',
            'dosage', 'form', 'route', 'frequency', 'times_per_day',
            'start_date', 'end_date', 'duration_days', 'instructions',
            'special_instructions', 'prescribed_by', 'prescription_number',
            'prescribed_date', 'quantity_prescribed', 'refills_allowed',
            'side_effects', 'interactions', 'purpose', 'is_critical',
            'schedules'
        ]
    
    def create(self, validated_data):
        schedules_data = validated_data.pop('schedules', [])
        
        # Set created_by
        validated_data['created_by'] = self.context['request'].user
        validated_data['refills_remaining'] = validated_data.get('refills_allowed', 0)
        
        medication = Medication.objects.create(**validated_data)
        
        # Create schedules
        for schedule_data in schedules_data:
            MedicationSchedule.objects.create(medication=medication, **schedule_data)
        
        return medication


class MedicationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing medications"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    is_active = serializers.ReadOnlyField()
    next_dose_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Medication
        fields = [
            'id', 'patient_name', 'medication_name', 'dosage', 'form',
            'frequency', 'start_date', 'end_date', 'status',
            'is_active', 'is_critical', 'next_dose_time'
        ]
    
    def get_next_dose_time(self, obj):
        """Get next scheduled dose time"""
        next_schedule = MedicationAdherence.objects.filter(
            medication=obj,
            status='SCHEDULED',
            scheduled_datetime__gte=timezone.now()
        ).order_by('scheduled_datetime').first()
        
        if next_schedule:
            return next_schedule.scheduled_datetime
        return None


class MedicationAdherenceSerializer(serializers.ModelSerializer):
    """Full adherence record serializer"""
    
    medication_name = serializers.CharField(source='medication.medication_name', read_only=True)
    is_overdue = serializers.ReadOnlyField()
    delay_minutes = serializers.ReadOnlyField()
    
    class Meta:
        model = MedicationAdherence
        fields = [
            'id', 'medication', 'medication_name', 'schedule',
            'scheduled_date', 'scheduled_time', 'scheduled_datetime',
            'actual_datetime', 'status', 'confirmed_by_patient',
            'confirmation_method', 'skip_reason', 'miss_reason',
            'notes', 'side_effects_reported', 'reminder_sent_at',
            'reminder_count', 'is_overdue', 'delay_minutes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MedicationAdherenceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating adherence status"""
    
    class Meta:
        model = MedicationAdherence
        fields = [
            'status', 'actual_datetime', 'confirmed_by_patient',
            'confirmation_method', 'skip_reason', 'notes',
            'side_effects_reported'
        ]
    
    def validate_status(self, value):
        """Validate status transitions"""
        instance = self.instance
        if instance and instance.status == 'TAKEN' and value != 'TAKEN':
            raise serializers.ValidationError(
                "Cannot change status once medication is marked as taken"
            )
        return value


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


class DailyMedicationScheduleSerializer(serializers.Serializer):
    """Serializer for daily medication schedule view"""
    
    medication_id = serializers.IntegerField()
    medication_name = serializers.CharField()
    dosage = serializers.CharField()
    form = serializers.CharField()
    instructions = serializers.CharField()
    is_critical = serializers.BooleanField()
    
    scheduled_time = serializers.TimeField()
    time_label = serializers.CharField()
    with_food = serializers.BooleanField()
    
    adherence_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    actual_datetime = serializers.DateTimeField(allow_null=True)
    is_overdue = serializers.BooleanField()
