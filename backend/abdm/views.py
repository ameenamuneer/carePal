from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from rest_framework import status
from abdm.services.registration import ABHARegistrationService
from abdm.serializers.registration import (
    RegistrationInitSerializer,
    OTPVerifySerializer,
    ABHACreateSerializer,
    LoginInitSerializer,
    LoginVerifySerializer
)
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_registration(request):
    """
    POST /api/v1/abdm/registration/init/
    
    Body: {"mobile": "9876543210"}
    """
    serializer = RegistrationInitSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    mobile = serializer.validated_data['mobile']
    service = ABHARegistrationService()
    
    try:
        result = service.initiate_registration(mobile)
        return Response(result, status=status.HTTP_200_OK)
        
    except ValueError as e:
        # Validation error
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        # API error
        logger.error(f"Registration initiation failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_otp(request):
    """
    POST /api/v1/abdm/registration/verify/
    
    Body: {
        "txn_id": "xxx",
        "otp": "123456"
    }
    """
    serializer = OTPVerifySerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    txn_id = serializer.validated_data['txn_id']
    otp = serializer.validated_data['otp']
    
    service = ABHARegistrationService()
    
    try:
        result = service.verify_registration_otp(txn_id, otp)
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"OTP verification failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_abha(request):
    """
    POST /api/v1/abdm/registration/create/
    
    Body: {
        "txn_id": "xxx",
        "abha_address": "myusername"
    }
    """
    serializer = ABHACreateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    txn_id = serializer.validated_data['txn_id']
    abha_address = serializer.validated_data['abha_address']
    
    # Get patient from request
    patient = request.user.patient_profile
    
    service = ABHARegistrationService()
    
    try:
        abha_profile = service.create_abha_address(txn_id, abha_address, patient)
        
        return Response({
            'abha_address': abha_profile.abha_address,
            'abha_number': abha_profile.abha_number,
            'message': 'ABHA created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"ABHA creation failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def initiate_login_view(request):
    """
    POST /api/v1/abdm/login/init/
    """
    serializer = LoginInitSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)
    
    mobile = serializer.validated_data['mobile']
    service = ABHARegistrationService()
    
    try:
        result = service.initiate_login(mobile)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"Login init failed: {str(e)}")
        return Response({'error': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_login_view(request):
    """
    POST /api/v1/abdm/login/verify/
    """
    serializer = LoginVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)
    
    txn_id = serializer.validated_data['txn_id']
    otp = serializer.validated_data['otp']
    
    service = ABHARegistrationService()
    
    try:
        # Pass patient to link profile if needed
        # Since this is public now, we can't trust request.user
        # The service layer should handle finding/creating the user based on ABHA data
        result = service.verify_login_otp(txn_id, otp)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"Login verify failed: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_login_view(request):
    """
    POST /api/v1/abdm/login/
    Complete login by selecting ABHA address (Step 3)
    Only needed when skip_state is 'abha_select'
    """
    from abdm.serializers.registration import LoginCompleteSerializer
    
    serializer = LoginCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)
    
    txn_id = serializer.validated_data['txn_id']
    abha_address = serializer.validated_data['abha_address']
    
    service = ABHARegistrationService()
    
    try:
        result = service.complete_login(txn_id, abha_address)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"Login completion failed: {str(e)}")
        return Response({'error': str(e)}, status=400)


# ==================== CONSENT & CONTEXT VIEWS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_consent_view(request):
    """
    POST /api/v1/abdm/consents/approve
    """
    from abdm.serializers.consent import ApproveConsentSerializer
    from abdm.services.eka_client import EKAClient
    
    serializer = ApproveConsentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)
        
    client = EKAClient()
    try:
        # Pass OID from user profile if available, else None
        oid = getattr(request.user.patient_profile, 'oid', None) if hasattr(request.user, 'patient_profile') else None
        
        client.approve_consent_request(request.data, oid=oid)
        return Response(status=204)
    except Exception as e:
        logger.error(f"Consent approval failed: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deny_consent_view(request):
    """
    POST /api/v1/abdm/consents/deny
    """
    from abdm.serializers.consent import DenyConsentSerializer
    from abdm.services.eka_client import EKAClient
    
    serializer = DenyConsentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)
        
    client = EKAClient()
    try:
        oid = getattr(request.user.patient_profile, 'oid', None) if hasattr(request.user, 'patient_profile') else None
        client.deny_consent_request(
            serializer.validated_data['id'], 
            serializer.validated_data['reason'],
            oid=oid
        )
        return Response(status=204)
    except Exception as e:
        logger.error(f"Consent denial failed: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def linked_providers_view(request):
    """
    GET /api/v1/abdm/care-contexts/providers
    """
    from abdm.services.eka_client import EKAClient
    client = EKAClient()
    try:
        oid = getattr(request.user.patient_profile, 'oid', None) if hasattr(request.user, 'patient_profile') else None
        # OID can also be passed in query params
        req_oid = request.query_params.get('oid') or oid
        
        result = client.get_linked_providers(oid=req_oid)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"Get linked providers failed: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def linked_contexts_view(request):
    """
    GET /api/v1/abdm/care-contexts/linked
    """
    from abdm.services.eka_client import EKAClient
    
    hip_id = request.query_params.get('hip_id')
    if not hip_id:
        return Response({'error': 'hip_id is required'}, status=400)
        
    client = EKAClient()
    try:
        oid = getattr(request.user.patient_profile, 'oid', None) if hasattr(request.user, 'patient_profile') else None
        req_oid = request.query_params.get('oid') or oid
        
        result = client.get_linked_care_contexts(hip_id=hip_id, oid=req_oid)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"Get linked contexts failed: {str(e)}")
        return Response({'error': str(e)}, status=400)


# ==================== DISCOVERY & LINKING VIEWS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def discover_contexts_view(request):
    """
    POST /api/v1/abdm/care-contexts/discover
    """
    from abdm.services.eka_client import EKAClient
    client = EKAClient()
    
    hip_id = request.data.get('hip_id')
    ref_id = request.data.get('ref_id') # e.g. mobile number
    
    if not hip_id or not ref_id:
        return Response({'error': 'hip_id and ref_id (mobile/id) are required'}, status=400)

    try:
        oid = getattr(request.user.patient_profile, 'oid', None) if hasattr(request.user, 'patient_profile') else None
        
        result = client.discover_care_contexts(hip_id, ref_id, oid=oid)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"Discovery failed: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_linking_view(request):
    """
    POST /api/v1/abdm/care-contexts/link/init
    """
    from abdm.services.eka_client import EKAClient
    client = EKAClient()
    
    txn_id = request.data.get('txn_id')
    patient_ref_id = request.data.get('patient_ref_id')
    cc_ref_id = request.data.get('cc_ref_id')
    
    if not txn_id or not patient_ref_id or not cc_ref_id:
        return Response({'error': 'txn_id, patient_ref_id, and cc_ref_id are required'}, status=400)

    try:
        oid = getattr(request.user.patient_profile, 'oid', None) if hasattr(request.user, 'patient_profile') else None
        
        result = client.initiate_link_care_contexts(txn_id, patient_ref_id, cc_ref_id, oid=oid)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"Link init failed: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_linking_view(request):
    """
    POST /api/v1/abdm/care-contexts/link/confirm
    """
    from abdm.services.eka_client import EKAClient
    client = EKAClient()
    
    txn_id = request.data.get('txn_id')
    otp = request.data.get('otp')
    
    if not txn_id or not otp:
        return Response({'error': 'txn_id and otp are required'}, status=400)

    try:
        oid = getattr(request.user.patient_profile, 'oid', None) if hasattr(request.user, 'patient_profile') else None
        
        result = client.confirm_link_care_contexts(txn_id, otp, oid=oid)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"Link confirm failed: {str(e)}")
        return Response({'error': str(e)}, status=400)


# ==================== REQUESTS & WEBHOOKS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_requests_view(request):
    """
    GET /api/v1/abdm/requests
    """
    from abdm.services.eka_client import EKAClient
    client = EKAClient()
    
    status = request.query_params.get('status', 'requested')
    req_type = request.query_params.get('type', 'all')
    
    try:
        oid = getattr(request.user.patient_profile, 'oid', None) if hasattr(request.user, 'patient_profile') else None
        
        result = client.get_patient_requests(status=status, type=req_type, oid=oid)
        return Response(result, status=200)
    except Exception as e:
        logger.error(f"List requests failed: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([AllowAny]) # Webhooks come from server-to-server
@api_view(['POST'])
@permission_classes([AllowAny]) # Webhooks come from server-to-server
def abdm_webhook_view(request):
    """
    POST /api/v1/abdm/webhook
    Handle Eka Webhooks
    Delegates to abdm.callbacks.webhook_handler.WebhookHandler
    """
    from abdm.callbacks.webhook_handler import WebhookHandler

    try:
        data = request.data
        event = data.get('event')
        payload = data.get('data', {})
        
        # Verify Signature (TODO)
        
        WebhookHandler.handle_event(event, payload)
        
        return Response({'status': 'received'}, status=200)
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        # Return 200 even on error to stop retries if it's a parsing error
        return Response({'error': str(e)}, status=200)






