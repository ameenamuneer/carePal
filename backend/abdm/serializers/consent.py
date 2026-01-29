from rest_framework import serializers

class ApproveConsentSerializer(serializers.Serializer):
    id = serializers.CharField(required=True)
    consent_artefacts = serializers.ListField(
        child=serializers.DictField(),
        required=True
    )
    access_mode = serializers.ChoiceField(choices=['view'], default='view')
    # Add other fields if needed, but these are the minimal required

class DenyConsentSerializer(serializers.Serializer):
    id = serializers.CharField(required=True)
    reason = serializers.CharField(required=True)

class LinkedContextsSerializer(serializers.Serializer):
    hip_id = serializers.CharField(required=True)
    oid = serializers.CharField(required=False)
