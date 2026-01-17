from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.shortcuts import redirect
from django.db.models import Count, Max
from datetime import datetime, timedelta
import secrets
from urllib.parse import urlencode

from .models import (
    CloudProvider, CloudAPICredential, DeviceSyncLog,
    DeviceCalibration, DataConflict, WebhookSubscription,
    BluetoothDeviceSession, DevicePriority
)
from .serializers import *
from vitals.models import DataSource, VitalReading, VitalType
from patients.models import PatientProfile
from .cloud_clients.fitbit_client import FitbitClient
from .cloud_clients.google_fit_client import GoogleFitClient
from .tasks import sync_device_data

import logging
logger = logging.getLogger(__name__)


class CloudProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for cloud providers catalog (read-only)
    """
    queryset = CloudProvider.objects.filter(is_active=True)
    serializer_class = CloudProviderSerializer
    permission_classes = [IsAuthenticated]


class CloudAPICredentialViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing cloud API credentials
    """
    serializer_class = CloudAPICredentialSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['patient', 'provider', 'status']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return CloudAPICredential.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return CloudAPICredential.objects.filter(patient_id__in=linked_patients)
        else:
            return CloudAPICredential.objects.all()
    
    @action(detail=True, methods=['post'])
    def sync_now(self, request, pk=None):
        """
        Trigger manual sync for this credential
        POST /api/v1/devices/cloud-credentials/{id}/sync_now/
        """
        credential = self.get_object()
        
        if credential.status != 'ACTIVE':
            return Response(
                {'error': 'Credential is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Trigger async sync
        sync_device_data.delay(credential.data_source.id)
        
        return Response({
            'message': 'Sync initiated',
            'credential_id': credential.id,
            'provider': credential.provider.display_name
        })
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """
        Revoke cloud API credential
        POST /api/v1/devices/cloud-credentials/{id}/revoke/
        """
        credential = self.get_object()
        
        credential.status = 'REVOKED'
        credential.consent_revoked_at = timezone.now()
        credential.save()
        
        # Deactivate associated data source
        if credential.data_source:
            credential.data_source.is_active = False
            credential.data_source.save()
        
        return Response({
            'message': 'Credential revoked successfully'
        })


class FitbitOAuthView(APIView):
    """
    Handle Fitbit OAuth flow
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Initiate Fitbit OAuth flow
        GET /api/v1/devices/cloud/fitbit/authorize/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            if request.user.user_type == 'PATIENT':
                patient = PatientProfile.objects.filter(user=request.user).first()
                patient_id = patient.id if patient else None
            else:
                return Response(
                    {'error': 'patient_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            provider = CloudProvider.objects.get(name='FITBIT', is_active=True)
        except CloudProvider.DoesNotExist:
            return Response(
                {'error': 'Fitbit provider not configured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        request.session['oauth_patient_id'] = patient_id
        request.session['oauth_provider'] = 'FITBIT'
        
        # Build authorization URL
        params = {
            'client_id': provider.client_id,
            'response_type': 'code',
            'scope': ' '.join(provider.scopes),
            'redirect_uri': request.build_absolute_uri('/api/v1/devices/cloud/fitbit/callback/'),
            'state': state
        }
        
        auth_url = f"{provider.authorization_url}?{urlencode(params)}"
        
        return Response({
            'authorization_url': auth_url
        })


class FitbitOAuthCallbackView(APIView):
    """
    Handle Fitbit OAuth callback
    """
    permission_classes = [AllowAny]  # Callback from Fitbit doesn't include auth
    
    def get(self, request):
        """
        GET /api/v1/devices/cloud/fitbit/callback/?code=xxx&state=xxx
        """
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        error = request.query_params.get('error')
        
        if error:
            return Response(
                {'error': f'OAuth error: {error}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify state
        session_state = request.session.get('oauth_state')
        if not state or state != session_state:
            return Response(
                {'error': 'Invalid state parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        patient_id = request.session.get('oauth_patient_id')
        
        try:
            provider = CloudProvider.objects.get(name='FITBIT')
            patient = PatientProfile.objects.get(id=patient_id)
            
            # Exchange code for tokens
            import requests
            response = requests.post(
                provider.token_url,
                auth=(provider.client_id, provider.client_secret),
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': request.build_absolute_uri('/api/v1/devices/cloud/fitbit/callback/')
                }
            )
            response.raise_for_status()
            
            token_data = response.json()
            
            # Get user info
            user_response = requests.get(
                f"{provider.api_base_url}/user/-/profile.json",
                headers={'Authorization': f"Bearer {token_data['access_token']}"}
            )
            user_info = user_response.json() if user_response.ok else {}
            
            # Create or update data source
            data_source, created = DataSource.objects.get_or_create(
                patient=patient,
                source_type='CLOUD_API',
                device_identifier=f"fitbit_{token_data.get('user_id', 'unknown')}",
                defaults={
                    'device_type': 'FITNESS_TRACKER',
                    'device_name': 'Fitbit',
                    'device_manufacturer': 'Fitbit',
                    'sync_frequency_minutes': 15,
                    'is_active': True
                }
            )
            
            # Create or update credential
            credential, created = CloudAPICredential.objects.update_or_create(
                patient=patient,
                provider=provider,
                defaults={
                    'data_source': data_source,
                    'provider_user_id': token_data.get('user_id', ''),
                    'provider_user_info': user_info,
                    'token_type': token_data.get('token_type', 'Bearer'),
                    'expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600)),
                    'scope': token_data.get('scope', ''),
                    'status': 'ACTIVE'
                }
            )
            
            # Store encrypted tokens
            credential.set_access_token(token_data['access_token'])
            credential.set_refresh_token(token_data.get('refresh_token', ''))
            credential.save()
            
            # Update data source last sync
            data_source.last_sync_at = timezone.now()
            data_source.save()
            
            # Trigger initial sync
            sync_device_data.delay(data_source.id)
            
            # Clear session
            del request.session['oauth_state']
            del request.session['oauth_patient_id']
            del request.session['oauth_provider']
            
            # Redirect to success page (frontend will handle)
            return redirect(f'/devices/connected?provider=fitbit&status=success')
        
        except Exception as e:
            logger.error(f"Fitbit OAuth callback error: {str(e)}")
            return Response(
                {'error': f'Failed to complete OAuth: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GoogleFitOAuthView(APIView):
    """
    Handle Google Fit OAuth flow
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Initiate Google Fit OAuth flow
        GET /api/v1/devices/cloud/google-fit/authorize/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            if request.user.user_type == 'PATIENT':
                patient = PatientProfile.objects.filter(user=request.user).first()
                patient_id = patient.id if patient else None
        
        try:
            provider = CloudProvider.objects.get(name='GOOGLE_FIT', is_active=True)
        except CloudProvider.DoesNotExist:
            return Response(
                {'error': 'Google Fit provider not configured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        request.session['oauth_patient_id'] = patient_id
        request.session['oauth_provider'] = 'GOOGLE_FIT'
        
        # Build authorization URL
        params = {
            'client_id': provider.client_id,
            'response_type': 'code',
            'scope': ' '.join(provider.scopes),
            'redirect_uri': request.build_absolute_uri('/api/v1/devices/cloud/google-fit/callback/'),
            'state': state,
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        auth_url = f"{provider.authorization_url}?{urlencode(params)}"
        
        return Response({
            'authorization_url': auth_url
        })


class GoogleFitOAuthCallbackView(APIView):
    """
    Handle Google Fit OAuth callback
    Similar structure to Fitbit callback
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """
        GET /api/v1/devices/cloud/google-fit/callback/?code=xxx&state=xxx
        """
        # Implementation similar to Fitbit callback
        # Exchange code for tokens, create credential, trigger sync
        pass  # Implementation details similar to Fitbit


class BluetoothDeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Bluetooth device management
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['patient', 'device_type', 'is_active']
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = DataSource.objects.filter(source_type='BLUETOOTH_DEVICE')
        
        if user.user_type == 'PATIENT':
            queryset = queryset.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            queryset = queryset.filter(patient_id__in=linked_patients)
        
        return queryset
    
    def get_serializer_class(self):
        from vitals.serializers import DataSourceSerializer
        return DataSourceSerializer
    
    @action(detail=False, methods=['post'])
    def ingest_data(self, request):
        """
        Ingest data from Bluetooth device (called by Flutter app)
        POST /api/v1/devices/bluetooth/ingest/
        """
        serializer = BluetoothDataIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        try:
            # Get data source
            data_source = DataSource.objects.get(
                id=data['data_source_id'],
                source_type='BLUETOOTH_DEVICE'
            )
            
            # Create or update session
            session, created = BluetoothDeviceSession.objects.get_or_create(
                session_id=data['session_id'],
                defaults={
                    'data_source': data_source,
                    'connected_at': data['connected_at'],
                    'status': 'CONNECTED',
                    'battery_level': data.get('battery_level'),
                    'signal_strength': data.get('signal_strength'),
                    'device_firmware': data.get('device_firmware', ''),
                    'device_hardware': data.get('device_hardware', ''),
                    'app_version': data.get('app_version', '')
                }
            )
            
            # Process readings
            created_readings = []
            for reading_data in data['readings']:
                # Create vital reading
                vital_reading = VitalReading.objects.create(
                    patient=data_source.patient,
                    vital_type_id=reading_data['vital_type_id'],
                    data_source=data_source,
                    measured_at=reading_data['measured_at'],
                    value=reading_data.get('value'),
                    values=reading_data.get('values', {}),
                    unit=reading_data['unit'],
                    data_quality=reading_data.get('data_quality', 'GOOD'),
                    notes=reading_data.get('notes', ''),
                    tags=reading_data.get('tags', [])
                )
                created_readings.append(vital_reading)
            
            # Update session
            session.readings_received = len(created_readings)
            session.save()
            
            # Update data source
            data_source.last_sync_at = timezone.now()
            if data.get('battery_level') is not None:
                data_source.metadata = data_source.metadata or {}
                data_source.metadata['battery_level'] = data['battery_level']
            data_source.save()
            
            return Response({
                'message': 'Data ingested successfully',
                'session_id': session.session_id,
                'readings_created': len(created_readings),
                'reading_ids': [r.id for r in created_readings]
            }, status=status.HTTP_201_CREATED)
        
        except DataSource.DoesNotExist:
            return Response(
                {'error': 'Data source not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error ingesting Bluetooth data: {str(e)}")
            return Response(
                {'error': f'Failed to ingest data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        """
        End Bluetooth session
        POST /api/v1/devices/bluetooth/{id}/end_session/
        """
        device = self.get_object()
        session_id = request.data.get('session_id')
        
        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = BluetoothDeviceSession.objects.get(
                data_source=device,
                session_id=session_id
            )
            
            session.disconnected_at = timezone.now()
            session.status = 'DISCONNECTED'
            
            if session.connected_at and session.disconnected_at:
                delta = session.disconnected_at - session.connected_at
                session.duration_seconds = int(delta.total_seconds())
            
            session.save()
            
            serializer = BluetoothDeviceSessionSerializer(session)
            return Response(serializer.data)
        
        except BluetoothDeviceSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class DeviceSyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing sync logs
    """
    serializer_class = DeviceSyncLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['data_source', 'status', 'sync_type']
    ordering = ['-started_at']
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = DeviceSyncLog.objects.all()
        
        if user.user_type == 'PATIENT':
            queryset = queryset.filter(data_source__patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            queryset = queryset.filter(data_source__patient_id__in=linked_patients)
        
        return queryset


class DataConflictViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing data conflicts
    """
    serializer_class = DataConflictSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['patient', 'vital_type', 'resolution_method']
    ordering = ['-conflict_time']
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = DataConflict.objects.all()
        
        if user.user_type == 'PATIENT':
            queryset = queryset.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            queryset = queryset.filter(patient_id__in=linked_patients)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """
        Resolve data conflict
        POST /api/v1/devices/conflicts/{id}/resolve/
        """
        conflict = self.get_object()
        serializer = DataConflictResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        conflict.resolution_method = data['resolution_method']
        conflict.selected_reading_id = data.get('selected_reading_id')
        conflict.resolution_notes = data.get('resolution_notes', '')
        conflict.resolved_by = request.user
        conflict.resolved_at = timezone.now()
        
        # Calculate resolved value based on method
        if data['resolution_method'] == 'USE_PRIMARY':
            # Use reading from primary device
            conflict.resolved_value = conflict.readings[0]['value']
        elif data['resolution_method'] == 'USE_AVERAGE':
            # Average all readings
            values = [r['value'] for r in conflict.readings]
            conflict.resolved_value = sum(values) / len(values)
        elif data['resolution_method'] == 'USE_LATEST':
            # Use most recent reading
            conflict.resolved_value = conflict.readings[-1]['value']
        elif data['resolution_method'] == 'MANUAL' and data.get('selected_reading_id'):
            # Use manually selected reading
            selected = next(
                (r for r in conflict.readings if r['id'] == data['selected_reading_id']),
                None
            )
            if selected:
                conflict.resolved_value = selected['value']
        
        conflict.save()
        
        output_serializer = DataConflictSerializer(conflict)
        return Response(output_serializer.data)


class DeviceStatusView(APIView):
    """
    Get device status summary for dashboard
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/v1/devices/status/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            if request.user.user_type == 'PATIENT':
                patient = PatientProfile.objects.filter(user=request.user).first()
                patient_id = patient.id if patient else None
        
        if not patient_id:
            return Response(
                {'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all devices for patient
        devices = DataSource.objects.filter(patient_id=patient_id)
        
        status_list = []
        
        for device in devices:
            # Get last reading
            last_reading = VitalReading.objects.filter(
                data_source=device
            ).order_by('-measured_at').first()
            
            # Get last sync
            last_sync = DeviceSyncLog.objects.filter(
                data_source=device
            ).order_by('-started_at').first()
            
            # Get latest session for Bluetooth devices
            battery_level = None
            if device.source_type == 'BLUETOOTH_DEVICE':
                latest_session = BluetoothDeviceSession.objects.filter(
                    data_source=device
                ).order_by('-connected_at').first()
                
                if latest_session:
                    battery_level = latest_session.battery_level
            
            # Determine connection status
            if device.source_type == 'BLUETOOTH_DEVICE':
                # Check if connected in last 5 minutes
                if device.last_sync_at and \
                   (timezone.now() - device.last_sync_at).total_seconds() < 300:
                    connection_status = 'connected'
                else:
                    connection_status = 'disconnected'
            else:  # Cloud API
                # Check credential status
                try:
                    credential = CloudAPICredential.objects.get(data_source=device)
                    if credential.status == 'ACTIVE':
                        connection_status = 'connected'
                    else:
                        connection_status = credential.status.lower()
                except CloudAPICredential.DoesNotExist:
                    connection_status = 'not_configured'
            
            # Total readings
            total_readings = VitalReading.objects.filter(
                data_source=device
            ).count()
            
            status_list.append({
                'device_id': device.id,
                'device_name': device.device_name,
                'device_type': device.device_type,
                'source_type': device.source_type,
                'is_active': device.is_active,
                'last_sync_at': device.last_sync_at,
                'last_reading_at': last_reading.measured_at if last_reading else None,
                'battery_level': battery_level,
                'connection_status': connection_status,
                'sync_status': last_sync.status if last_sync else None,
                'total_readings': total_readings
            })
        
        serializer = DeviceStatusSerializer(status_list, many=True)
        return Response(serializer.data)
