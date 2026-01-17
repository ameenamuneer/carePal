from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models import PatientProfile, EmergencyContact, HealthCondition
from .serializers import (
    PatientProfileSerializer,
    PatientProfileCreateSerializer,
    PatientProfileListSerializer,
    EmergencyContactSerializer,
    HealthConditionSerializer
)

class PatientProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing patient profiles
    
    list: Get all patient profiles (admin/doctor access)
    retrieve: Get specific patient profile
    create: Create patient profile for logged-in user
    update: Update patient profile
    partial_update: Partially update patient profile
    destroy: Deactivate patient profile
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['gender', 'blood_group', 'preferred_language', 'city', 'state', 'is_active']
    search_fields = ['user__first_name', 'user__last_name', 'user__phone_number', 'city']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Filter queryset based on user type
        - Patients see only their own profile
        - Family members see linked patients
        - Doctors/Admins see all patients
        """
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return PatientProfile.objects.filter(user=user)
        elif user.user_type == 'FAMILY':
            # Get patients linked to this family member
            # Note: Family app might not be fully implemented yet, handling gracefully if model doesn't exist
            try:
                from family.models import FamilyMember
                linked_patients = FamilyMember.objects.filter(
                    user=user
                ).values_list('patient_id', flat=True)
                return PatientProfile.objects.filter(id__in=linked_patients)
            except ImportError:
                return PatientProfile.objects.none()
        else:  # DOCTOR or ADMIN
            return PatientProfile.objects.all()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PatientProfileListSerializer
        elif self.action == 'create':
            return PatientProfileCreateSerializer
        return PatientProfileSerializer
    
    def create(self, request, *args, **kwargs):
        """Create patient profile for current user"""
        # Check if user already has a patient profile
        if hasattr(request.user, 'patient_profile'):
            return Response(
                {'error': 'Patient profile already exists for this user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify user is a PATIENT
        if request.user.user_type != 'PATIENT':
            return Response(
                {'error': 'Only users with PATIENT type can create patient profiles'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient_profile = serializer.save()
        
        # Return full profile data
        output_serializer = PatientProfileSerializer(patient_profile)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete - deactivate instead of hard delete"""
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(
            {'message': 'Patient profile deactivated successfully'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def health_summary(self, request, pk=None):
        """
        Get health summary for a patient
        GET /api/v1/patients/{id}/health_summary/
        """
        patient = self.get_object()
        
        summary = {
            'patient_id': patient.id,
            'patient_name': patient.user.get_full_name(),
            'age': patient.user.age,
            'gender': patient.get_gender_display(),
            'blood_group': patient.blood_group,
            'bmi': patient.bmi,
            'bmi_category': patient.bmi_category,
            'health_conditions': patient.health_conditions,
            'allergies': patient.allergies,
            'current_medications': patient.current_medications,
            'emergency_contacts': EmergencyContactSerializer(
                patient.emergency_contacts.filter(is_active=True), 
                many=True
            ).data,
            'last_updated': patient.updated_at
        }
        
        return Response(summary, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """
        Get current user's patient profile
        GET /api/v1/patients/my_profile/
        """
        try:
            patient_profile = PatientProfile.objects.get(user=request.user)
            serializer = PatientProfileSerializer(patient_profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PatientProfile.DoesNotExist:
            return Response(
                {'error': 'Patient profile not found for current user'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def add_health_condition(self, request, pk=None):
        """
        Add a health condition to patient
        POST /api/v1/patients/{id}/add_health_condition/
        Body: {"condition": "Diabetes Type 2"}
        """
        patient = self.get_object()
        condition = request.data.get('condition')
        
        if not condition:
            return Response(
                {'error': 'Condition name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if condition not in patient.health_conditions:
            patient.health_conditions.append(condition)
            patient.save()
            return Response(
                {'message': 'Health condition added successfully',
                 'health_conditions': patient.health_conditions},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {'message': 'Condition already exists'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def remove_health_condition(self, request, pk=None):
        """
        Remove a health condition from patient
        POST /api/v1/patients/{id}/remove_health_condition/
        Body: {"condition": "Diabetes Type 2"}
        """
        patient = self.get_object()
        condition = request.data.get('condition')
        
        if condition in patient.health_conditions:
            patient.health_conditions.remove(condition)
            patient.save()
            return Response(
                {'message': 'Health condition removed successfully',
                 'health_conditions': patient.health_conditions},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {'error': 'Condition not found'},
            status=status.HTTP_404_NOT_FOUND
        )


class EmergencyContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing emergency contacts
    """
    
    serializer_class = EmergencyContactSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter emergency contacts based on user access"""
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            # Get contacts for current patient
            return EmergencyContact.objects.filter(
                patient__user=user,
                is_active=True
            )
        elif user.user_type == 'FAMILY':
            # Get contacts for linked patients
            try:
                from family.models import FamilyMember
                linked_patients = FamilyMember.objects.filter(
                    user=user
                ).values_list('patient_id', flat=True)
                return EmergencyContact.objects.filter(
                    patient_id__in=linked_patients,
                    is_active=True
                )
            except ImportError:
                 return EmergencyContact.objects.none()
        else:
            return EmergencyContact.objects.filter(is_active=True)
    
    def create(self, request, *args, **kwargs):
        """Create emergency contact for patient"""
        # Get patient_id from request
        patient_id = request.data.get('patient_id')
        
        if not patient_id:
            # If not provided, try to get current user's patient profile
            try:
                patient = PatientProfile.objects.get(user=request.user)
                patient_id = patient.id
            except PatientProfile.DoesNotExist:
                return Response(
                    {'error': 'patient_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Verify access to patient
        try:
            patient = PatientProfile.objects.get(id=patient_id)
            # Check if user has access to this patient
            if request.user.user_type == 'PATIENT' and patient.user != request.user:
                return Response(
                    {'error': 'You do not have access to this patient'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except PatientProfile.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create contact
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = serializer.save(patient=patient)
        
        return Response(
            EmergencyContactSerializer(contact).data,
            status=status.HTTP_201_CREATED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete emergency contact"""
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(
            {'message': 'Emergency contact removed successfully'},
            status=status.HTTP_200_OK
        )


class HealthConditionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for health conditions catalog (read-only for users)
    """
    
    queryset = HealthCondition.objects.filter(is_active=True)
    serializer_class = HealthConditionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'description']
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """
        Get health conditions grouped by category
        GET /api/v1/health-conditions/by_category/
        """
        conditions = {}
        for category, label in HealthCondition.CATEGORY_CHOICES:
            conditions[category] = HealthConditionSerializer(
                HealthCondition.objects.filter(category=category, is_active=True),
                many=True
            ).data
        
        return Response(conditions, status=status.HTTP_200_OK)
