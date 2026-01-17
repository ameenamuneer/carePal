from rest_framework import serializers
from .models import (
    VitalType, DataSource, VitalReading, 
    VitalReadingEdit, ContinuousVitalSession, VitalTrendAnalysis
)
from patients.serializers import PatientProfileListSerializer


class VitalTypeSerializer(serializers.ModelSerializer):
    """Serializer for vital types catalog"""
    
    class Meta:
        model = VitalType
        fields = [
            'id', 'name', 'code', 'category', 'unit', 
            'description', 'normal_range', 'is_continuous',
            'requires_multiple_values', 'is_active'
        ]
        read_only_fields = ['id']


class DataSourceSerializer(serializers.ModelSerializer):
    """Serializer for data sources"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = DataSource
        fields = [
            'id', 'patient', 'patient_name', 'source_type', 'device_type',
            'device_name', 'device_model', 'device_manufacturer',
            'device_identifier', 'is_active', 'last_sync_at',
            'sync_frequency_minutes', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_sync_at']
    
    def validate_device_identifier(self, value):
        """Ensure unique device identifier per patient"""
        patient = self.initial_data.get('patient')
        if patient:
            existing = DataSource.objects.filter(
                patient_id=patient,
                device_identifier=value
            ).exclude(id=self.instance.id if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "This device is already registered for this patient"
                )
        return value


class VitalReadingSerializer(serializers.ModelSerializer):
    """Full serializer for vital readings"""
    
    vital_type_detail = VitalTypeSerializer(source='vital_type', read_only=True)
    data_source_detail = DataSourceSerializer(source='data_source', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    display_value = serializers.CharField(source='get_display_value', read_only=True)
    entered_by_name = serializers.CharField(source='entered_by.get_full_name', read_only=True)
    
    class Meta:
        model = VitalReading
        fields = [
            'id', 'patient', 'patient_name', 'vital_type', 'vital_type_detail',
            'data_source', 'data_source_detail', 'measured_at', 'received_at',
            'value', 'values', 'unit', 'display_value',
            'is_anomaly', 'anomaly_severity', 'anomaly_reason',
            'data_quality', 'notes', 'tags', 'session_id',
            'entered_by', 'entered_by_name', 'is_edited', 'edited_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'received_at', 'is_anomaly', 'anomaly_severity',
            'anomaly_reason', 'created_at', 'updated_at'
        ]
    
    def validate(self, attrs):
        """Validate that either value or values is provided"""
        vital_type = attrs.get('vital_type')
        value = attrs.get('value')
        values = attrs.get('values', {})
        
        if vital_type:
            if vital_type.requires_multiple_values:
                if not values:
                    raise serializers.ValidationError(
                        f"{vital_type.name} requires multiple values (e.g., systolic/diastolic)"
                    )
            else:
                if value is None:
                    raise serializers.ValidationError(
                        f"{vital_type.name} requires a single value"
                    )
        
        return attrs


class VitalReadingCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating vital readings"""
    
    class Meta:
        model = VitalReading
        fields = [
            'patient', 'vital_type', 'data_source', 'measured_at',
            'value', 'values', 'unit', 'notes', 'tags', 'session_id',
            'entered_by', 'data_quality'
        ]
    
    def create(self, validated_data):
        # Set entered_by if manual entry
        if not validated_data.get('data_source'):
            validated_data['entered_by'] = self.context['request'].user
        
        return super().create(validated_data)


class VitalReadingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing vital readings"""
    
    vital_name = serializers.CharField(source='vital_type.name', read_only=True)
    vital_code = serializers.CharField(source='vital_type.code', read_only=True)
    display_value = serializers.CharField(source='get_display_value', read_only=True)
    
    class Meta:
        model = VitalReading
        fields = [
            'id', 'vital_name', 'vital_code', 'display_value',
            'measured_at', 'is_anomaly', 'anomaly_severity',
            'data_quality', 'is_edited'
        ]


class VitalReadingEditSerializer(serializers.ModelSerializer):
    """Serializer for editing vital readings (admin only)"""
    
    edit_reason = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = VitalReading
        fields = ['value', 'values', 'notes', 'tags', 'edit_reason']
    
    def update(self, instance, validated_data):
        edit_reason = validated_data.pop('edit_reason')
        
        # Create edit history record
        VitalReadingEdit.objects.create(
            vital_reading=instance,
            edited_by=self.context['request'].user,
            previous_value=instance.value,
            previous_values=instance.values,
            previous_notes=instance.notes,
            new_value=validated_data.get('value', instance.value),
            new_values=validated_data.get('values', instance.values),
            new_notes=validated_data.get('notes', instance.notes),
            edit_reason=edit_reason
        )
        
        # Update the reading
        instance.is_edited = True
        instance.edited_at = timezone.now()
        instance.edited_by = self.context['request'].user
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class VitalReadingEditHistorySerializer(serializers.ModelSerializer):
    """Serializer for viewing edit history"""
    
    edited_by_name = serializers.CharField(source='edited_by.get_full_name', read_only=True)
    
    class Meta:
        model = VitalReadingEdit
        fields = [
            'id', 'edited_by', 'edited_by_name', 'previous_value',
            'previous_values', 'previous_notes', 'new_value',
            'new_values', 'new_notes', 'edit_reason', 'edited_at'
        ]


class ContinuousVitalSessionSerializer(serializers.ModelSerializer):
    """Serializer for continuous monitoring sessions"""
    
    vital_name = serializers.CharField(source='vital_type.name', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = ContinuousVitalSession
        fields = [
            'id', 'patient', 'patient_name', 'vital_type', 'vital_name',
            'data_source', 'session_id', 'started_at', 'ended_at',
            'status', 'duration_minutes', 'total_readings',
            'average_value', 'min_value', 'max_value',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_readings', 'average_value',
            'min_value', 'max_value', 'created_at', 'updated_at'
        ]
    
    def get_duration_minutes(self, obj):
        if obj.ended_at:
            delta = obj.ended_at - obj.started_at
            return round(delta.total_seconds() / 60, 2)
        return None


class VitalTrendAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for trend analysis"""
    
    vital_name = serializers.CharField(source='vital_type.name', read_only=True)
    vital_code = serializers.CharField(source='vital_type.code', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    
    class Meta:
        model = VitalTrendAnalysis
        fields = [
            'id', 'patient', 'patient_name', 'vital_type', 'vital_name', 'vital_code',
            'period_start', 'period_end', 'period_label',
            'reading_count', 'average_value', 'min_value', 'max_value',
            'std_deviation', 'trend_direction', 'trend_percentage',
            'anomaly_count', 'critical_anomaly_count', 'insights', 'computed_at'
        ]


class DashboardVitalSummarySerializer(serializers.Serializer):
    """Serializer for dashboard vital summary"""
    
    vital_type = serializers.CharField()
    vital_code = serializers.CharField()
    latest_reading = VitalReadingListSerializer()
    readings_today = serializers.IntegerField()
    average_today = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    trend_7days = VitalTrendAnalysisSerializer(allow_null=True)
    has_anomalies = serializers.BooleanField()
    anomaly_count_today = serializers.IntegerField()
