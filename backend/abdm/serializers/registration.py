from rest_framework import serializers
import re

class RegistrationInitSerializer(serializers.Serializer):
    mobile = serializers.CharField(
        max_length=15,
        help_text="Mobile number (10 digits, with or without +91)"
    )
    
    def validate_mobile(self, value):
        """Basic validation - full validation in service layer"""
        # Remove spaces
        value = value.strip().replace(' ', '')
        
        # Must be numeric (possibly with + at start)
        if not re.match(r'^\+?\d+$', value):
            raise serializers.ValidationError(
                "Mobile number must contain only digits"
            )
        
        return value


class OTPVerifySerializer(serializers.Serializer):
    txn_id = serializers.CharField(max_length=100)
    otp = serializers.CharField(min_length=6, max_length=6)
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be 6 digits")
        return value


class ABHACreateSerializer(serializers.Serializer):
    txn_id = serializers.CharField(max_length=100)
    abha_address = serializers.CharField(
        max_length=50,
        help_text="ABHA address without @abdm suffix"
    )
    
    def validate_abha_address(self, value):
        # ABHA address validation rules
        if not re.match(r'^[a-z0-9._-]+$', value.lower()):
            raise serializers.ValidationError(
                "ABHA address can only contain lowercase letters, "
                "numbers, dots, hyphens, and underscores"
            )
        
        if len(value) < 4:
            raise serializers.ValidationError(
                "ABHA address must be at least 4 characters"
            )
        
        return value.lower()

class LoginInitSerializer(serializers.Serializer):
    mobile = serializers.CharField(
        max_length=15,
        help_text="Mobile number (10 digits)"
    )
    
    def validate_mobile(self, value):
        value = value.strip().replace(' ', '')
        if not re.match(r'^\+?\d+$', value):
            raise serializers.ValidationError("Invalid mobile number")
        return value

class LoginVerifySerializer(serializers.Serializer):
    txn_id = serializers.CharField(max_length=100)
    otp = serializers.CharField(min_length=6, max_length=6)
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be 6 digits")
        return value

class LoginCompleteSerializer(serializers.Serializer):
    txn_id = serializers.CharField(required=True)
    abha_address = serializers.CharField(required=True)

