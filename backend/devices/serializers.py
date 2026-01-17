from rest_framework import serializers
from django.utils import timezone
from .models import (
    CloudProvider, CloudAPICredential, DeviceSyncLog,
    DeviceCalibration, DataConflict, WebhookSubscription,
    BluetoothDeviceSession, DevicePriority
)
from vitals.models import DataSource


class CloudProviderSerializer(serializers.ModelSerializer):
    """Serializer for cloud providers catalog"""
    
    class Meta:
        model = CloudProvider
        fields = [
            'id', 'name', 'display_name', 'authorization_url',
            'supported_vitals', 'supports_webhooks', 
            'sync_interval_minutes', 'is_active'
        ]
        read_only_fields = ['id']


class CloudAPICredentialSerializer(serializers.ModelSerializer):
    """Serializer for cloud API credentials (without tokens)"""
    
    provider_name = serializers.CharField(source='provider.display_name', read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    is_token_expired = serializers.ReadOnlyField()
    needs_refresh = serializers.ReadOnlyField()
    
    class Meta:
        model = CloudAPICredential
        fields = [
            'id', 'patient', 'patient_name', 'provider', 'provider_name',
            'data_source', 'token_type', 'expires_at', 'scope',
            'provider_user_id', 'provider_user_info', 'status',
            'last_sync_at', 'last_error', 'consent_given_at',
            'is_token_expired', 'needs_refresh', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'token_type', 'expires_at', 'scope', 'provider_user_id',
            'provider_user_info', 'status', 'last_sync_at', 'last_error',
            'consent_given_at', 'created_at', 'updated_at'
        ]


class DeviceSyncLogSerializer(serializers.ModelSerializer):
    """Serializer for sync logs"""
    
    device_name = serializers.CharField(source='data_source.device_name', read_only=True)
    provider_name = serializers.SerializerMethodField()
    
    class Meta:
        model = DeviceSyncLog
        fields = [
            'id', 'data_source', 'device_name', 'cloud_credential',
            'provider_name', 'sync_type', 'started_at', 'completed_at',
            'duration_seconds', 'status', 'records_fetched',
            'records_created', 'records_updated', 'records_failed',
            'sync_from_date', 'sync_to_date', 'error_message',
            'error_details', 'metadata'
        ]
        read_only_fields = ['id', 'started_at']
    
    def get_provider_name(self, obj):
        if obj.cloud_credential:
            return obj.cloud_credential.provider.display_name
        return None


class DeviceCalibrationSerializer(serializers.ModelSerializer):
    """Serializer for device calibration"""
    
    device_name = serializers.CharField(source='data_source.device_name', read_only=True)
    calibrated_by_name = serializers.CharField(source='calibrated_by.get_full_name', read_only=True)
    
    class Meta:
        model = DeviceCalibration
        fields = [
            'id', 'data_source', 'device_name', 'calibrated_at',
            'calibrated_by', 'calibrated_by_name', 'calibration_type',
            'calibration_values', 'reference_device', 'reference_value',
            'device_value', 'deviation', 'notes', 'next_calibration_due',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DataConflictSerializer(serializers.ModelSerializer):
    """Serializer for data conflicts"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    vital_name = serializers.CharField(source='vital_type.name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    
    class Meta:
        model = DataConflict
        fields = [
            'id', 'patient', 'patient_name', 'vital_type', 'vital_name',
            'conflict_time', 'time_window_minutes', 'readings',
            'max_deviation', 'deviation_percentage', 'resolution_method',
            'selected_reading_id', 'resolved_value', 'resolved_by',
            'resolved_by_name', 'resolved_at', 'resolution_notes',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DataConflictResolveSerializer(serializers.Serializer):
    """Serializer for resolving conflicts"""
    
    resolution_method = serializers.ChoiceField(
        choices=DataConflict.RESOLUTION_CHOICES
    )
    selected_reading_id = serializers.IntegerField(required=False, allow_null=True)
    resolution_notes = serializers.CharField(required=False, allow_blank=True)


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for webhook subscriptions"""
    
    provider_name = serializers.CharField(source='cloud_credential.provider.display_name', read_only=True)
    
    class Meta:
        model = WebhookSubscription
        fields = [
            'id', 'cloud_credential', 'provider_name', 'subscription_id',
            'callback_url', 'event_types', 'verification_code',
            'verified_at', 'status', 'last_notification_at',
            'notification_count', 'expires_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'verified_at', 'last_notification_at',
            'notification_count', 'created_at', 'updated_at'
        ]


class BluetoothDeviceSessionSerializer(serializers.ModelSerializer):
    """Serializer for Bluetooth sessions"""
    
    device_name = serializers.CharField(source='data_source.device_name', read_only=True)
    
    class Meta:
        model = BluetoothDeviceSession
        fields = [
            'id', 'data_source', 'device_name', 'session_id',
            'connected_at', 'disconnected_at', 'duration_seconds',
            'signal_strength', 'battery_level', 'readings_received',
            'bytes_transferred', 'status', 'error_message',
            'device_firmware', 'device_hardware', 'app_version'
        ]
        read_only_fields = ['id']


class BluetoothDataIngestSerializer(serializers.Serializer):
    """Serializer for ingesting Bluetooth device data"""
    
    session_id = serializers.CharField(required=True)
    data_source_id = serializers.IntegerField(required=True)
    connected_at = serializers.DateTimeField(required=True)
    
    # Device info
    battery_level = serializers.IntegerField(required=False, min_value=0, max_value=100)
    signal_strength = serializers.IntegerField(required=False)
    device_firmware = serializers.CharField(required=False, allow_blank=True)
    device_hardware = serializers.CharField(required=False, allow_blank=True)
    app_version = serializers.CharField(required=False, allow_blank=True)
    
    # Readings data
    readings = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        help_text="List of vital readings"
    )
    
    def validate_readings(self, value):
        """Validate readings format"""
        if not value:
            raise serializers.ValidationError("At least one reading is required")
        
        for reading in value:
            required_fields = ['vital_type_id', 'measured_at', 'unit']
            for field in required_fields:
                if field not in reading:
                    raise serializers.ValidationError(f"Reading missing required field: {field}")
            
            # Must have either 'value' or 'values'
            if 'value' not in reading and 'values' not in reading:
                raise serializers.ValidationError("Reading must have 'value' or 'values' field")
        
        return value


class DevicePrioritySerializer(serializers.ModelSerializer):
    """Serializer for device priority"""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    vital_name = serializers.CharField(source='vital_type.name', read_only=True)
    
    class Meta:
        model = DevicePriority
        fields = [
            'id', 'patient', 'patient_name', 'vital_type', 'vital_name',
            'priority_order', 'use_average_if_close', 'threshold_percentage',
            'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']


class DeviceStatusSerializer(serializers.Serializer):
    """Serializer for device status summary"""
    
    device_id = serializers.IntegerField()
    device_name = serializers.CharField()
    device_type = serializers.CharField()
    source_type = serializers.CharField()
    is_active = serializers.BooleanField()
    last_sync_at = serializers.DateTimeField(allow_null=True)
    last_reading_at = serializers.DateTimeField(allow_null=True)
    battery_level = serializers.IntegerField(allow_null=True)
    connection_status = serializers.CharField()
    sync_status = serializers.CharField(allow_null=True)
    total_readings = serializers.IntegerField()
