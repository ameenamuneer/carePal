from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg, Min, Max, Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import (
    VitalType, DataSource, VitalReading,
    VitalReadingEdit, ContinuousVitalSession, VitalTrendAnalysis
)
from .serializers import *
from patients.models import PatientProfile


class VitalTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for vital types catalog (read-only)
    """
    queryset = VitalType.objects.filter(is_active=True)
    serializer_class = VitalTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'is_continuous']
    search_fields = ['name', 'code', 'description']


class DataSourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing data sources
    """
    serializer_class = DataSourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['patient', 'source_type', 'device_type', 'is_active']
    search_fields = ['device_name', 'device_model', 'device_identifier']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return DataSource.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return DataSource.objects.filter(patient_id__in=linked_patients)
        else:
            return DataSource.objects.all()
    
    @action(detail=True, methods=['post'])
    def sync_now(self, request, pk=None):
        """
        Trigger immediate sync for cloud-based data sources
        POST /api/v1/vitals/data-sources/{id}/sync_now/
        """
        source = self.get_object()
        
        if source.source_type != 'CLOUD_API':
            return Response(
                {'error': 'Only cloud API sources can be synced'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Here you would trigger the actual sync
        # For now, just update last_sync_at
        source.last_sync_at = timezone.now()
        source.save()
        
        return Response({
            'message': 'Sync initiated',
            'last_sync_at': source.last_sync_at
        })


class VitalReadingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for vital readings
    Supports create, read, update (admin only), delete (soft)
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'patient', 'vital_type', 'data_source', 'is_anomaly',
        'anomaly_severity', 'session_id', 'is_edited'
    ]
    search_fields = ['notes']
    ordering_fields = ['measured_at', 'received_at', 'created_at']
    ordering = ['-measured_at']
    
    def get_queryset(self):
        user = self.request.user
        queryset = VitalReading.objects.filter(is_deleted=False)
        
        if user.user_type == 'PATIENT':
            queryset = queryset.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            queryset = queryset.filter(patient_id__in=linked_patients)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(measured_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(measured_at__lte=end_date)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return VitalReadingListSerializer
        elif self.action == 'create':
            return VitalReadingCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return VitalReadingEditSerializer
        return VitalReadingSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new vital reading"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vital_reading = serializer.save()
        
        # Return full details
        output_serializer = VitalReadingSerializer(vital_reading)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update vital reading (admin only)"""
        if not request.user.is_staff and request.user.user_type != 'ADMIN':
            return Response(
                {'error': 'Only administrators can edit vital readings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete vital reading"""
        instance = self.get_object()
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save()
        
        return Response(
            {'message': 'Vital reading deleted successfully'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def edit_history(self, request, pk=None):
        """
        Get edit history for a vital reading
        GET /api/v1/vitals/readings/{id}/edit_history/
        """
        vital_reading = self.get_object()
        edits = VitalReadingEdit.objects.filter(vital_reading=vital_reading)
        serializer = VitalReadingEditHistorySerializer(edits, many=True)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """
        Get latest readings for each vital type
        GET /api/v1/vitals/readings/latest/?patient_id=1
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
        
        # Get latest reading for each vital type
        vital_types = VitalType.objects.filter(is_active=True)
        latest_readings = []
        
        for vital_type in vital_types:
            reading = VitalReading.objects.filter(
                patient_id=patient_id,
                vital_type=vital_type,
                is_deleted=False
            ).order_by('-measured_at').first()
            
            if reading:
                latest_readings.append(reading)
        
        serializer = VitalReadingListSerializer(latest_readings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trends(self, request):
        """
        Get trend data for a specific vital type
        GET /api/v1/vitals/readings/trends/?patient_id=1&vital_type_id=1&period=7days
        """
        patient_id = request.query_params.get('patient_id')
        vital_type_id = request.query_params.get('vital_type_id')
        period = request.query_params.get('period', '7days')  # 24h, 7days, 30days
        
        if not patient_id or not vital_type_id:
            return Response(
                {'error': 'patient_id and vital_type_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate date range
        if period == '24h':
            start_date = timezone.now() - timedelta(hours=24)
        elif period == '7days':
            start_date = timezone.now() - timedelta(days=7)
        elif period == '30days':
            start_date = timezone.now() - timedelta(days=30)
        else:
            return Response(
                {'error': 'Invalid period. Use 24h, 7days, or 30days'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get readings
        readings = VitalReading.objects.filter(
            patient_id=patient_id,
            vital_type_id=vital_type_id,
            measured_at__gte=start_date,
            is_deleted=False
        ).order_by('measured_at')
        
        # Calculate statistics
        stats = readings.aggregate(
            count=Count('id'),
            avg_value=Avg('value'),
            min_value=Min('value'),
            max_value=Max('value'),
            anomaly_count=Count('id', filter=Q(is_anomaly=True))
        )
        
        serializer = VitalReadingListSerializer(readings, many=True)
        
        return Response({
            'period': period,
            'start_date': start_date,
            'end_date': timezone.now(),
            'statistics': stats,
            'readings': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def anomalies(self, request):
        """
        Get all anomalous readings
        GET /api/v1/vitals/readings/anomalies/?patient_id=1&severity=CRITICAL
        """
        patient_id = request.query_params.get('patient_id')
        severity = request.query_params.get('severity')
        
        queryset = self.get_queryset().filter(is_anomaly=True)
        
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        if severity:
            queryset = queryset.filter(anomaly_severity=severity)
        
        serializer = VitalReadingSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create vital readings (for device sync)
        POST /api/v1/vitals/readings/bulk_create/
        Body: {"readings": [...]}
        """
        readings_data = request.data.get('readings', [])
        
        if not readings_data:
            return Response(
                {'error': 'No readings provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_readings = []
        errors = []
        
        for idx, reading_data in enumerate(readings_data):
            serializer = VitalReadingCreateSerializer(
                data=reading_data,
                context={'request': request}
            )
            
            if serializer.is_valid():
                reading = serializer.save()
                created_readings.append(reading)
            else:
                errors.append({
                    'index': idx,
                    'errors': serializer.errors
                })
        
        return Response({
            'created_count': len(created_readings),
            'error_count': len(errors),
            'created_readings': VitalReadingListSerializer(created_readings, many=True).data,
            'errors': errors
        }, status=status.HTTP_201_CREATED if created_readings else status.HTTP_400_BAD_REQUEST)


class ContinuousVitalSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for continuous monitoring sessions
    """
    serializer_class = ContinuousVitalSessionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'vital_type', 'status']
    ordering = ['-started_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return ContinuousVitalSession.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return ContinuousVitalSession.objects.filter(patient_id__in=linked_patients)
        else:
            return ContinuousVitalSession.objects.all()
    
    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        """
        End a continuous monitoring session
        POST /api/v1/vitals/sessions/{id}/end_session/
        """
        session = self.get_object()
        
        if session.status != 'ACTIVE':
            return Response(
                {'error': 'Session is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session.ended_at = timezone.now()
        session.status = 'COMPLETED'
        
        # Calculate final statistics
        readings = VitalReading.objects.filter(
            session_id=session.session_id,
            is_deleted=False
        )
        
        stats = readings.aggregate(
            total=Count('id'),
            avg=Avg('value'),
            min=Min('value'),
            max=Max('value')
        )
        
        session.total_readings = stats['total'] or 0
        session.average_value = stats['avg']
        session.min_value = stats['min']
        session.max_value = stats['max']
        session.save()
        
        serializer = self.get_serializer(session)
        return Response(serializer.data)


class VitalTrendAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing trend analysis (read-only, computed by background tasks)
    """
    serializer_class = VitalTrendAnalysisSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'vital_type', 'period_label', 'trend_direction']
    ordering = ['-period_end']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return VitalTrendAnalysis.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return VitalTrendAnalysis.objects.filter(patient_id__in=linked_patients)
        else:
            return VitalTrendAnalysis.objects.all()


class DashboardViewSet(viewsets.ViewSet):
    """
    Special viewset for dashboard data aggregation
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def vitals_summary(self, request):
        """
        Get complete vitals summary for dashboard
        GET /api/v1/vitals/dashboard/vitals_summary/?patient_id=1
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
        
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        summary = []
        vital_types = VitalType.objects.filter(is_active=True)
        
        for vital_type in vital_types:
            # Latest reading
            latest = VitalReading.objects.filter(
                patient_id=patient_id,
                vital_type=vital_type,
                is_deleted=False
            ).order_by('-measured_at').first()
            
            # Readings today
            today_readings = VitalReading.objects.filter(
                patient_id=patient_id,
                vital_type=vital_type,
                measured_at__gte=today_start,
                is_deleted=False
            )
            
            readings_count = today_readings.count()
            avg_today = today_readings.aggregate(Avg('value'))['value__avg']
            anomaly_count = today_readings.filter(is_anomaly=True).count()
            
            # 7-day trend
            trend_7days = VitalTrendAnalysis.objects.filter(
                patient_id=patient_id,
                vital_type=vital_type,
                period_label='last_7days'
            ).order_by('-computed_at').first()
            
            # Recent history for plotting (last 15 readings)
            recent_readings = VitalReading.objects.filter(
                patient_id=patient_id,
                vital_type=vital_type,
                is_deleted=False
            ).order_by('-measured_at')[:15]
            
            # Convert to list and reverse to chronological order (oldest -> newest) for plotting
            recent_history = VitalReadingListSerializer(reversed(recent_readings), many=True).data

            summary.append({
                'vital_type': vital_type.name,
                'vital_code': vital_type.code,
                'latest_reading': VitalReadingListSerializer(latest).data if latest else None,
                'readings_today': readings_count,
                'average_today': avg_today,
                'trend_7days': VitalTrendAnalysisSerializer(trend_7days).data if trend_7days else None,
                'has_anomalies': anomaly_count > 0,
                'anomaly_count_today': anomaly_count,
                'recent_history': recent_history  # New field for sparklines
            })
        
        return Response(summary)
