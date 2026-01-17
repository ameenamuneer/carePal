from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import AgentSession, AgentMessage
from .serializers import (
    AgentSessionSerializer,
    AgentSessionListSerializer,
    AgentMessageSerializer
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
