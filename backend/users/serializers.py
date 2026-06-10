from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User

class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer"""
    age = serializers.ReadOnlyField()
    patient_profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'user_type',
            'first_name', 'last_name', 'date_of_birth', 'age',
            'profile_picture', 'is_active', 'created_at', 'updated_at',
            'patient_profile'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_patient_profile(self, obj):
        """Include patient profile data if user is a patient"""
        if obj.user_type == 'PATIENT' and hasattr(obj, 'patient_profile'):
            return {
                'id': obj.patient_profile.id,
                'gender': obj.patient_profile.gender,
                'blood_group': obj.patient_profile.blood_group,
            }
        return None


class UserRegistrationSerializer(serializers.ModelSerializer):
    """User registration serializer with password validation"""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'phone_number', 'password', 'password_confirm',
            'user_type', 'first_name', 'last_name', 'date_of_birth'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    """Login serializer - accepts username/email/phone"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        # Try to find user by username, email, or phone
        user = None
        if '@' in username:
            user = User.objects.filter(email=username).first()
        elif username.startswith('+') or username.isdigit():
            user = User.objects.filter(phone_number=username).first()
        else:
            user = User.objects.filter(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                raise serializers.ValidationError("User account is disabled.")
            attrs['user'] = user
            return attrs
        
        raise serializers.ValidationError("Invalid credentials.")


class TokenSerializer(serializers.Serializer):
    """Token response serializer"""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


from .models import ClinicalRelationship


class ClinicalRelationshipSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = ClinicalRelationship
        fields = [
            'id', 'doctor', 'doctor_name', 'patient', 'patient_name',
            'role', 'is_active', 'notes',
            'can_view_vitals', 'can_view_activity_log', 'can_view_medications',
            'can_edit_medications', 'can_view_alerts',
            'can_view_appointments', 'can_edit_appointments',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'doctor', 'created_at', 'updated_at', 'doctor_name', 'patient_name']

    def get_doctor_name(self, obj):
        return obj.doctor.get_full_name()

    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name()
