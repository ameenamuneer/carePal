from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import datetime, timedelta

from .models import (
    AlertType, Alert, AlertDelivery, AlertRule,
    NotificationPreference, AlertEscalation, AlertStatistics
)
from .serializers import *
from patients.models import PatientProfile
from .tasks import process_alert_delivery, escalate_alert

import logging
logger = logging.getLogger(__name__)


class AlertTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for alert types catalog (read-only)
    """
    queryset = AlertType.objects.filter(is_active=True)
    serializer_class = AlertTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'default_severity']
    search_fields = ['name', 'code']


class AlertViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing alerts
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'severity', 'status', 'alert_type', 'is_escalated']
    ordering_fields = ['created_at', 'severity']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = Alert.objects.all()
        
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
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AlertListSerializer
        return AlertSerializer
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """
        Acknowledge an alert
        POST /api/v1/alerts/alerts/{id}/acknowledge/
        Body: {"acknowledgment_notes": "Patient called, all good"}
        """
        alert = self.get_object()
        
        if alert.status in ['ACKNOWLEDGED', 'RESOLVED']:
            return Response(
                {'error': 'Alert already acknowledged or resolved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = AlertAcknowledgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        alert.status = 'ACKNOWLEDGED'
        alert.acknowledged_at = timezone.now()
        alert.acknowledged_by = request.user
        alert.acknowledgment_notes = serializer.validated_data.get('acknowledgment_notes', '')
        alert.save()
        
        output_serializer = AlertSerializer(alert)
        return Response(output_serializer.data)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """
        Resolve an alert
        POST /api/v1/alerts/alerts/{id}/resolve/
        Body: {"resolution_notes": "Patient vitals normalized"}
        """
        alert = self.get_object()
        
        if alert.status == 'RESOLVED':
            return Response(
                {'error': 'Alert already resolved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = AlertResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        alert.status = 'RESOLVED'
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.resolution_notes = serializer.validated_data['resolution_notes']
        
        # Also acknowledge if not already
        if not alert.acknowledged_at:
            alert.acknowledged_at = timezone.now()
            alert.acknowledged_by = request.user
        
        alert.save()
        
        output_serializer = AlertSerializer(alert)
        return Response(output_serializer.data)
    
    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """
        Manually escalate an alert
        POST /api/v1/alerts/alerts/{id}/escalate/
        Body: {"reason": "No response from patient", "severity": "EMERGENCY"}
        """
        alert = self.get_object()
        
        reason = request.data.get('reason', 'Manual escalation')
        new_severity = request.data.get('severity')
        
        # Trigger escalation task
        escalate_alert.delay(alert.id, reason=reason, manual=True, new_severity=new_severity)
        
        return Response({
            'message': 'Alert escalation initiated',
            'alert_id': alert.id
        })
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Get all active (unresolved) alerts
        GET /api/v1/alerts/alerts/active/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        queryset = self.get_queryset().filter(
            status__in=['PENDING', 'SENT', 'DELIVERED', 'ACKNOWLEDGED', 'ESCALATED']
        )
        
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        serializer = AlertListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def critical(self, request):
        """
        Get critical and emergency alerts
        GET /api/v1/alerts/alerts/critical/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        queryset = self.get_queryset().filter(
            severity__in=['CRITICAL', 'EMERGENCY'],
            status__in=['PENDING', 'SENT', 'DELIVERED', 'ACKNOWLEDGED', 'ESCALATED']
        )
        
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        serializer = AlertSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unacknowledged(self, request):
        """
        Get unacknowledged alerts
        GET /api/v1/alerts/alerts/unacknowledged/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        queryset = self.get_queryset().filter(
            acknowledged_at__isnull=True,
            status__in=['PENDING', 'SENT', 'DELIVERED', 'ESCALATED']
        )
        
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        serializer = AlertListSerializer(queryset, many=True)
        return Response(serializer.data)


class AlertRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing alert rules
    """
    serializer_class = AlertRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['patient', 'alert_type', 'rule_type', 'is_active']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = AlertRule.objects.all()
        
        if user.user_type == 'PATIENT':
            queryset = queryset.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            queryset = queryset.filter(patient_id__in=linked_patients)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test if a rule would trigger
        POST /api/v1/alerts/rules/{id}/test/
        Body: {"test_data": {...}}
        """
        rule = self.get_object()
        test_data = request.data.get('test_data', {})
        
        # Here you would implement rule evaluation logic
        # For now, just return if rule can trigger
        can_trigger = rule.can_trigger()
        
        return Response({
            'can_trigger': can_trigger,
            'rule_active': rule.is_active,
            'last_triggered': rule.last_triggered_at,
            'trigger_count': rule.trigger_count
        })


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification preferences
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Users can only view/edit their own preferences
        return NotificationPreference.objects.filter(user=user)
    
    @action(detail=False, methods=['get', 'put', 'patch'])
    def my_preferences(self, request):
        """
        Get or update current user's preferences
        GET/PUT/PATCH /api/v1/alerts/preferences/my_preferences/
        """
        try:
            preference = NotificationPreference.objects.get(user=request.user)
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            preference = NotificationPreference.objects.create(user=request.user)
        
        if request.method == 'GET':
            serializer = NotificationPreferenceSerializer(preference)
            return Response(serializer.data)
        else:
            serializer = NotificationPreferenceSerializer(
                preference,
                data=request.data,
                partial=request.method == 'PATCH'
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)


class AlertDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing alert deliveries
    """
    serializer_class = AlertDeliverySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['alert', 'recipient', 'channel', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        # Users can see deliveries for alerts they're involved with
        queryset = AlertDelivery.objects.filter(
            Q(recipient=user) |
            Q(alert__patient__user=user)
        )
        
        if user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            queryset = AlertDelivery.objects.filter(
                Q(recipient=user) |
                Q(alert__patient_id__in=linked_patients)
            )
        
        return queryset


class AlertStatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing alert statistics
    """
    serializer_class = AlertStatisticsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['patient', 'period_label']
    ordering = ['-period_end']
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = AlertStatistics.objects.all()
        
        if user.user_type == 'PATIENT':
            queryset = queryset.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            queryset = queryset.filter(patient_id__in=linked_patients)
        
        return queryset


class AlertDashboardView(APIView):
    """
    Get alert dashboard summary
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/v1/alerts/dashboard/?patient_id=1
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
        
        # Get active alerts
        active_alerts = Alert.objects.filter(
            patient_id=patient_id,
            status__in=['PENDING', 'SENT', 'DELIVERED', 'ACKNOWLEDGED', 'ESCALATED']
        )
        
        # Count by severity
        severity_counts = active_alerts.values('severity').annotate(
            count=Count('id')
        )
        alerts_by_severity = {item['severity']: item['count'] for item in severity_counts}
        
        # Count by category
        category_counts = active_alerts.values('alert_type__category').annotate(
            count=Count('id')
        )
        alerts_by_category = {item['alert_type__category']: item['count'] for item in category_counts}
        
        # Recent alerts (last 24 hours)
        yesterday = timezone.now() - timedelta(hours=24)
        recent_alerts = Alert.objects.filter(
            patient_id=patient_id,
            created_at__gte=yesterday
        ).order_by('-created_at')[:10]
        
        dashboard_data = {
            'total_active': active_alerts.count(),
            'critical_count': active_alerts.filter(severity='CRITICAL').count(),
            'emergency_count': active_alerts.filter(severity='EMERGENCY').count(),
            'unacknowledged_count': active_alerts.filter(acknowledged_at__isnull=True).count(),
            'escalated_count': active_alerts.filter(is_escalated=True).count(),
            'recent_alerts': AlertListSerializer(recent_alerts, many=True).data,
            'alerts_by_severity': alerts_by_severity,
            'alerts_by_category': alerts_by_category
        }
        
        serializer = AlertDashboardSerializer(dashboard_data)
        return Response(serializer.data)
