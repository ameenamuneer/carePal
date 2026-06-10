from rest_framework import status, generics, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import BasicAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from .models import User, ClinicalRelationship
from .serializers import (
    UserRegistrationSerializer,
    LoginSerializer,
    UserSerializer,
    TokenSerializer,
    ClinicalRelationshipSerializer,
)
from .permissions import IsDoctor, IsAdmin

class UserRegistrationView(generics.CreateAPIView):
    """
    Register a new user
    POST /api/v1/auth/register/
    """
    queryset = User.objects.all()
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    User login
    POST /api/v1/auth/login/
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    User logout (blacklist refresh token)
    POST /api/v1/auth/logout/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get/Update current user profile
    GET/PUT/PATCH /api/v1/auth/profile/
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ClinicalRelationshipViewSet(viewsets.ModelViewSet):
    """
    Manage doctor–patient links.

    Doctors see only their own relationships.
    Admins see all.
    Patients can GET their own (read-only via /my-doctors/).
    """
    serializer_class = ClinicalRelationshipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'DOCTOR':
            return ClinicalRelationship.objects.filter(doctor=user).select_related(
                'doctor', 'patient__user'
            )
        if user.user_type == 'ADMIN':
            return ClinicalRelationship.objects.all().select_related(
                'doctor', 'patient__user'
            )
        # PATIENT / FAMILY: read-only via dedicated action
        return ClinicalRelationship.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        # Doctors create their own relationships; admins can specify the doctor field
        if user.user_type == 'DOCTOR':
            serializer.save(doctor=user)
        else:
            serializer.save()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), (IsDoctor() or IsAdmin())]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='my-doctors')
    def my_doctors(self, request):
        """
        GET /api/v1/auth/clinical-relationships/my-doctors/
        Patients retrieve all doctors linked to them.
        """
        if request.user.user_type != 'PATIENT':
            return Response({'detail': 'Only patients can use this endpoint.'}, status=403)
        if not hasattr(request.user, 'patient_profile'):
            return Response({'detail': 'No patient profile found.'}, status=404)
        qs = ClinicalRelationship.objects.filter(
            patient=request.user.patient_profile, is_active=True
        ).select_related('doctor', 'patient__user')
        return Response(ClinicalRelationshipSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='my-patients')
    def my_patients(self, request):
        """
        GET /api/v1/auth/clinical-relationships/my-patients/
        Doctors retrieve all patients linked to them.
        """
        if request.user.user_type != 'DOCTOR':
            return Response({'detail': 'Only doctors can use this endpoint.'}, status=403)
        qs = ClinicalRelationship.objects.filter(
            doctor=request.user, is_active=True
        ).select_related('doctor', 'patient__user')
        return Response(ClinicalRelationshipSerializer(qs, many=True).data)
