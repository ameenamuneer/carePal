from rest_framework import serializers
from .models import PatientProfile, EmergencyContact, HealthCondition
from users.serializers import UserSerializer

class EmergencyContactSerializer(serializers.ModelSerializer):
    """Serializer for emergency contacts"""
    
    class Meta:
        model = EmergencyContact
        fields = [
            'id', 'name', 'relationship', 'phone_number', 'alternate_phone',
            'email', 'is_primary', 'priority_order', 'notes', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if not value.startswith('+'):
            raise serializers.ValidationError("Phone number must include country code (e.g., +91)")
        return value


class PatientProfileSerializer(serializers.ModelSerializer):
    """Full patient profile serializer"""
    
    # Include user information
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    
    # Include related data
    emergency_contacts = EmergencyContactSerializer(many=True, read_only=True)
    
    # Computed fields
    bmi = serializers.ReadOnlyField()
    bmi_category = serializers.ReadOnlyField()
    full_address = serializers.ReadOnlyField()
    age = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientProfile
        fields = [
            'id', 'user', 'user_id', 'gender', 'blood_group', 
            'height_cm', 'weight_kg', 'bmi', 'bmi_category',
            'address_line1', 'address_line2', 'city', 'state', 
            'pincode', 'country', 'full_address',
            'preferred_language', 'health_conditions', 'allergies',
            'current_medications', 'medical_notes', 'last_hospital_visit',
            'emergency_contacts', 'age', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_age(self, obj):
        """Get age from user's date of birth"""
        return obj.user.age if obj.user else None
    
    def validate_user_id(self, value):
        """Validate that user exists and is a PATIENT"""
        from users.models import User
        try:
            user = User.objects.get(id=value)
            if user.user_type != 'PATIENT':
                raise serializers.ValidationError("User must be of type PATIENT")
            if hasattr(user, 'patient_profile'):
                raise serializers.ValidationError("Patient profile already exists for this user")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")


class PatientProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating patient profile"""
    
    class Meta:
        model = PatientProfile
        fields = [
            'gender', 'blood_group', 'height_cm', 'weight_kg',
            'address_line1', 'address_line2', 'city', 'state', 
            'pincode', 'country', 'preferred_language', 
            'health_conditions', 'allergies', 'current_medications',
            'medical_notes', 'last_hospital_visit'
        ]
    
    def create(self, validated_data):
        # Get user from context
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class PatientProfileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing patients"""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    age = serializers.SerializerMethodField()
    condition_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientProfile
        fields = [
            'id', 'user_name', 'user_phone', 'age', 'gender',
            'city', 'state', 'preferred_language', 'condition_count',
            'is_active', 'updated_at'
        ]
    
    def get_age(self, obj):
        return obj.user.age if obj.user else None
    
    def get_condition_count(self, obj):
        return len(obj.health_conditions) if obj.health_conditions else 0


class HealthConditionSerializer(serializers.ModelSerializer):
    """Serializer for health conditions catalog"""
    
    class Meta:
        model = HealthCondition
        fields = [
            'id', 'name', 'category', 'description', 
            'common_symptoms', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
