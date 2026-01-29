from rest_framework import serializers
from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    """
    Appointment serializer
    Returns appointment data from CarePAL DB
    """
    
    patient_name = serializers.CharField(
        source='patient.user.get_full_name',
        read_only=True
    )
    is_upcoming = serializers.BooleanField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient',
            'patient_name',
            'eka_appointment_id',
            'eka_doctor_id',
            'eka_clinic_id',
            'doctor_name',
            'clinic_name',
            'appointment_date',
            'mode',
            'status',
            'is_upcoming',
            'is_past',
            'booking_metadata',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'eka_appointment_id',
            'created_at',
            'updated_at',
        ]
