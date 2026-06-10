from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .models import AgentSession, AgentMessage, PatientActivityLog
from .serializers import (
    AgentSessionSerializer,
    AgentSessionListSerializer,
    AgentMessageSerializer,
    PatientActivityLogSerializer,
)

class AgentSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for AI Agent sessions
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Patients see their own sessions
        if hasattr(user, 'patient_profile'):
            return AgentSession.objects.filter(patient=user.patient_profile)
        # Family members see their patients' sessions (TODO: add detailed logic)
        return AgentSession.objects.filter(user=user)

    def get_serializer_class(self):
        if self.action == 'list':
            return AgentSessionListSerializer
        return AgentSessionSerializer

    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        """End an active session"""
        session = self.get_object()
        session.status = 'COMPLETED'
        session.calculate_duration()
        session.save()
        return Response({'status': 'session ended'})


class PatientActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only endpoint for retrieving AI-observed patient activity logs.

    Access control:
      - PATIENT  : their own logs
      - FAMILY   : linked patients where can_view_medical_history=True
      - DOCTOR   : linked patients where can_view_activity_log=True
      - ADMIN    : all

    Filters:
      ?activity_type=MEAL|EXERCISE|SLEEP|SYMPTOM|MEDICATION|MOOD|BEHAVIOR|...
      ?is_notable=true
      ?date_from=YYYY-MM-DD
      ?date_to=YYYY-MM-DD
      ?tags=dizziness   (substring match inside the JSON tags array)
    """

    serializer_class = PatientActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['activity_type', 'is_notable', 'ai_confidence']
    ordering_fields = ['observed_at', 'logged_at']
    ordering = ['-observed_at']

    def get_queryset(self):
        user = self.request.user

        if user.user_type == 'PATIENT':
            if not hasattr(user, 'patient_profile'):
                return PatientActivityLog.objects.none()
            qs = PatientActivityLog.objects.filter(patient=user.patient_profile)

        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            allowed_patient_ids = FamilyMember.objects.filter(
                user=user, is_active=True, can_view_activity_log=True
            ).values_list('patient_id', flat=True)
            qs = PatientActivityLog.objects.filter(patient_id__in=allowed_patient_ids)

        elif user.user_type == 'DOCTOR':
            from users.models import ClinicalRelationship
            allowed_patient_ids = ClinicalRelationship.objects.filter(
                doctor=user, is_active=True, can_view_activity_log=True
            ).values_list('patient_id', flat=True)
            qs = PatientActivityLog.objects.filter(patient_id__in=allowed_patient_ids)

        elif user.user_type == 'ADMIN':
            qs = PatientActivityLog.objects.all()

        else:
            return PatientActivityLog.objects.none()

        # Date range filters
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(observed_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(observed_at__date__lte=date_to)

        # Tag substring filter
        tag = self.request.query_params.get('tags')
        if tag:
            qs = qs.filter(tags__contains=[tag])

        return qs.select_related('patient__user', 'session')
