from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
import logging
from datetime import datetime

from .models import Appointment
from .serializers import AppointmentSerializer
from patients.models import PatientProfile
from ekacare.authentication import EkaCareAuth, EkaCareAPIException
from ekacare.patient_integration import EkaCarePatientIntegration

logger = logging.getLogger(__name__)


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    Appointment Management
    Books appointments via Eka.Care and stores in CarePAL DB
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AppointmentSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'PATIENT':
            return Appointment.objects.filter(patient__user=user)
        return Appointment.objects.all()
    
    @action(detail=False, methods=['get'])
    def available_slots(self, request):
        """
        Get available appointment slots from Eka.Care
        (Read-only, doesn't store in DB)
        """
        try:
            doctor_id = request.query_params.get('doctor_id')
            clinic_id = request.query_params.get('clinic_id')
            date = request.query_params.get('date')
            
            if not all([doctor_id, clinic_id, date]):
                return Response(
                    {'error': 'doctor_id, clinic_id, and date required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Fetch slots from Eka.Care
            result = EkaCareAuth.make_request(
                'GET',
                '/dr/v1/slots',
                params={
                    'doctor_id': doctor_id,
                    'clinic_id': clinic_id,
                    'start_date': date,
                    'end_date': date
                }
            )
            
            return Response(result)
            
        except EkaCareAPIException as e:
            logger.error(f"Failed to get slots: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def book(self, request):
        """
        Book appointment - USES EKA PATIENT ID
        """
        try:
            patient = request.user.patient_profile
            
            # Ensure patient exists in Eka.Care
            if not patient.has_eka_patient:
                # Auto-create if not exists
                eka_patient_id = EkaCarePatientIntegration.ensure_patient_in_ekacare(
                    patient
                )
                patient.refresh_from_db()
            
            doctor_id = request.data.get('doctor_id')
            clinic_id = request.data.get('clinic_id')
            appointment_time = request.data.get('appointment_time')
            
            if not all([doctor_id, clinic_id, appointment_time]):
                return Response(
                     {'error': 'doctor_id, clinic_id, and appointment_time required'},
                     status=status.HTTP_400_BAD_REQUEST
                )
            
            # Book via Eka.Care using eka_patient_id
            eka_result = EkaCareAuth.make_request(
                'POST',
                '/dr/v1/appointments',
                data={
                    'isBusinessOrDoctorAssosiatedWithEka': True,
                    'clinic_id': clinic_id,
                    'doctor_id': doctor_id,
                    
                    # Use eka_patient_id (NOT CarePAL ID, NOT ABHA)
                    'patient_id': patient.eka_patient_id,
                    
                    # Also send partner_patient_id for mapping
                    'partner_patient_id': patient.partner_patient_id,
                    
                    'appointment_details': {
                        'start_time': appointment_time,
                        'mode': request.data.get('mode', 'INCLINIC')
                    },
                    'patient_details': {
                        'dob': patient.date_of_birth.strftime('%Y-%m-%d') 
                               if patient.date_of_birth else '',
                        'first_name': patient.user.first_name,
                        'gender': patient.gender
                    }
                }
            )
            
            # Store in CarePAL DB
            appointment = Appointment.objects.create(
                patient=patient,
                eka_appointment_id=eka_result.get('appointment_id'),
                eka_doctor_id=doctor_id,
                eka_clinic_id=clinic_id,
                doctor_name=request.data.get('doctor_name', 'Unknown'),
                clinic_name=request.data.get('clinic_name', 'Unknown'),
                appointment_date=datetime.fromtimestamp(appointment_time),
                mode=request.data.get('mode', 'INCLINIC'),
                status='BOOKED',
                booking_metadata={
                    'eka_response': eka_result,
                    'booked_at': timezone.now().isoformat()
                }
            )
            
            serializer = AppointmentSerializer(appointment)
            
            return Response({
                'success': True,
                'appointment': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except EkaCareAPIException as e:
            logger.error(f"Appointment booking failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
