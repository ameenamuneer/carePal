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
from ekacare.authentication import EkaCareAuth, EkaCareAPIException
from ekacare.patient_integration import EkaCarePatientIntegration
import logging

logger = logging.getLogger(__name__)

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
    
    # ==================== EKA.CARE PATIENT CREATION ====================
    
    @action(detail=False, methods=['post'])
    def create_eka_patient(self, request):
        """
        Create patient in Eka.Care Patient Directory
        Links Eka patient_id to CarePAL patient
        """
        try:
            patient = request.user.patient_profile
            
            # Check if already created
            if patient.has_eka_patient:
                return Response({
                    'success': True,
                    'message': 'Patient already exists in Eka.Care',
                    'eka_patient_id': patient.eka_patient_id,
                    'partner_patient_id': patient.partner_patient_id,
                    'patient': PatientProfileSerializer(patient).data
                })
            
            # Create in Eka.Care and link
            eka_patient_id = EkaCarePatientIntegration.ensure_patient_in_ekacare(
                patient
            )
            
            # Return updated patient from CarePAL DB
            patient.refresh_from_db()
            serializer = self.get_serializer(patient)
            
            return Response({
                'success': True,
                'message': 'Patient created in Eka.Care and linked',
                'eka_patient_id': eka_patient_id,
                'partner_patient_id': patient.partner_patient_id,
                'patient': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except EkaCareAPIException as e:
            logger.error(f"Eka patient creation failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # ==================== ABHA REGISTRATION ====================
    
    @action(detail=False, methods=['post'])
    def register_abha_step1(self, request):
        """Step 1: Generate OTP for Aadhaar"""
        try:
            aadhaar_number = request.data.get('aadhaar_number')
            
            if not aadhaar_number or len(aadhaar_number) != 12:
                return Response(
                    {'error': 'Valid 12-digit Aadhaar required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Updated Endpoint: init
            result = EkaCareAuth.make_request(
                'POST',
                '/abdm/na/v1/registration/aadhaar/init',
                data={'aadhaar_number': aadhaar_number}
            )
            
            logger.info(f"ABHA Init Result: {result}")
            
            # Updated Key: txn_id (snake_case)
            txn_id = result.get('txn_id')
            request.session['abha_txn_id'] = txn_id
            
            return Response({
                'success': True,
                'message': 'OTP sent to Aadhaar-linked mobile',
                'txn_id': txn_id
            })
            
        except EkaCareAPIException as e:
            logger.error(f"ABHA Step 1 Failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def register_abha_step2(self, request):
        """Step 2: Verify OTP"""
        try:
            otp = request.data.get('otp')
            # ALLOW txn_id from body OR session
            txn_id = request.data.get('txn_id') or request.session.get('abha_txn_id')
            
            # Mobile is required by Eka.Care /verify endpoint
            # Default to patient's registered phone if not provided
            mobile = request.data.get('mobile')
            if not mobile:
                # Phone is on User model, not PatientProfile
                mobile = request.user.phone_number
                # Strip +91 if present for 10-digit requirement
                if mobile and mobile.startswith('+91'):
                    mobile = mobile[3:]
            
            if not otp or not txn_id or not mobile:
                missing = []
                if not otp: missing.append("OTP")
                if not txn_id: missing.append("txn_id")
                if not mobile: missing.append("mobile number (in profile or request)")
                
                return Response(
                    {'error': f"Missing required fields: {', '.join(missing)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Updated Endpoint: verify (based on docs)
            result = EkaCareAuth.make_request(
                'POST',
                '/abdm/na/v1/registration/aadhaar/verify',
                data={
                    'txn_id': txn_id, 
                    'otp': otp,
                    'mobile': mobile
                }
            )
            
            logger.info(f"ABHA Verify Result: {result}")
            
            new_txn_id = result.get('txn_id')
            request.session['abha_txn_id'] = new_txn_id
            
            return Response({
                'success': True,
                'message': 'OTP verified',
                'txn_id': new_txn_id,
                'mobile_used': mobile
            })
            
        except EkaCareAPIException as e:
            logger.error(f"ABHA Step 2 Failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def register_abha_step3(self, request):
        """
        Step 3: Create ABHA and link to patient
        Also updates Eka.Care patient if exists
        """
        try:
            abha_address = request.data.get('abha_address')
            # ALLOW txn_id from body OR session
            txn_id = request.data.get('txn_id') or request.session.get('abha_txn_id')
            
            if not abha_address or not txn_id:
                return Response(
                    {'error': 'ABHA address and txn_id required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not abha_address.endswith('@abdm'):
                abha_address = f"{abha_address}@abdm"
            
            # Updated Endpoint: create-phr
            result = EkaCareAuth.make_request(
                'POST',
                '/abdm/na/v1/registration/aadhaar/create-phr',
                data={'txn_id': txn_id, 'abha_address': abha_address}
            )
            
            logger.info(f"ABHA Create Result: {result}")
            
            # Response parsing: profile['abha_number']
            profile = result.get('profile', {})
            abha_number = profile.get('abha_number')
            
            if not abha_number:
                # Fallback if structure is different
                abha_number = result.get('abha_number')

            patient = request.user.patient_profile
            
            # Update patient with ABHA (also updates Eka.Care if linked)
            EkaCarePatientIntegration.update_patient_abha(
                patient,
                abha_number,
                abha_address
            )
            
            # Clear session
            request.session.pop('abha_txn_id', None)
            
            # Return from CarePAL DB
            patient.refresh_from_db()
            serializer = self.get_serializer(patient)
            
            return Response({
                'success': True,
                'message': 'ABHA created and linked',
                'abha_number': abha_number,
                'abha_address': abha_address,
                'patient': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except EkaCareAPIException as e:
            logger.error(f"ABHA Step 3 Failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def register_abha_resend_otp(self, request):
        """Resend OTP for Aadhaar registration"""
        try:
            # ALLOW txn_id from body OR session
            txn_id = request.data.get('txn_id') or request.session.get('abha_txn_id')
            
            if not txn_id:
                return Response(
                    {'error': 'txn_id required to resend OTP'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Resend OTP Endpoint
            result = EkaCareAuth.make_request(
                'POST',
                '/abdm/na/v1/registration/aadhaar/resend',
                data={'txn_id': txn_id}
            )
            
            logger.info(f"ABHA Resend OTP Result: {result}")
            
            new_txn_id = result.get('txn_id')
            request.session['abha_txn_id'] = new_txn_id
            
            return Response({
                'success': True,
                'message': 'OTP resent successfully',
                'txn_id': new_txn_id,
                'hint': result.get('hint')
            })
            
        except EkaCareAPIException as e:
            logger.error(f"ABHA Resend OTP Failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def scan_and_share(self, request):
        """
        Scan & Share: Share profile with hospital via QR code
        Expects: hip_id, counter_id, latitude (opt), longitude (opt)
        """
        try:
            hip_id = request.data.get('hip_id')
            counter_id = request.data.get('counter_id')
            lat = request.data.get('latitude')
            lon = request.data.get('longitude')
            
            if not hip_id or not counter_id:
                return Response(
                    {'error': 'hip_id and counter_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = request.user
            profile = user.patient_profile
            
            if not profile.abha_number and not profile.eka_patient_id:
                 return Response(
                    {'error': 'Patient must have ABHA or Eka Profile to share'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Construct Patient Payload
            dob = user.date_of_birth
            if not dob:
                return Response(
                    {'error': 'Date of Birth is required in profile to share'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Mobile formatting
            mobile = user.phone_number
            if mobile and mobile.startswith('+91'):
                mobile = mobile[3:]
                
            abha_address = profile.abha_address or f"{mobile}@abdm" # Fallback guess

            patient_payload = {
                "name": user.get_full_name(),
                "gender": profile.gender, # 'M', 'F', 'O'
                "day_of_birth": str(dob.day),
                "month_of_birth": str(dob.month),
                "year_of_birth": str(dob.year),
                "mobile": mobile,
                "abha_address": abha_address,
                "address": {
                    "line": profile.address_line1 or " Indiranagar",
                    "district": profile.city or "Bangalore",
                    "state": profile.state or "Karnataka",
                    "pin_code": profile.pincode or "560038"
                }
            }

            location_payload = {
                "latitude": str(lat) if lat else "12.9716",
                "longitude": str(lon) if lon else "77.5946"
            }

            payload = {
                "hip_id": hip_id,
                "counter_id": counter_id,
                "patient": patient_payload,
                "location": location_payload
            }
            
            # Call Eka.Care API
            result = EkaCareAuth.make_request(
                'POST',
                '/abdm/v2/profile/share',
                data=payload
            )
            
            return Response({
                'success': True,
                'message': 'Profile shared successfully',
                'request_id': result.get('request_id'),
                'status': result.get('status'),
                'token_number': result.get('token_number') # If available immed.
            })
            
        except EkaCareAPIException as e:
            logger.error(f"Scan & Share Failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    @action(detail=False, methods=['get'])
    def list_health_requests(self, request):
        """
        List Consents and Subscriptions
        Query Params: status (requested, granted...), type (consent, subscription, all)
        """
        try:
            status_filter = request.query_params.get('status', 'requested')
            req_type = request.query_params.get('type', 'all')
            
            # Validate params to match Eka allowed values? 
            # Letting API handle validation for flexibility
            
            params = {
                'status': status_filter,
                'type': req_type
            }
            
            result = EkaCareAuth.make_request(
                'GET',
                '/abdm/v1/requests',
                params=params
            )
            
            return Response(result)
            
        except EkaCareAPIException as e:
            logger.error(f"List Requests Failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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
