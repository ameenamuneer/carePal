from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    FamilyMember, FamilyInvitation, FamilyNote,
    FamilyActivityLog, FamilyCommunication, CareSchedule,
    FamilyDashboardSettings
)
from .serializers import *
from patients.models import PatientProfile
from vitals.models import VitalReading
from medications.models import Medication, MedicationAdherence
from alerts.models import Alert

import logging
logger = logging.getLogger(__name__)


class FamilyMemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing family members
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['patient', 'relationship', 'is_active', 'is_primary_caregiver']
    search_fields = ['user__first_name', 'user__last_name']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            # Patients can see family members linked to them
            return FamilyMember.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            # Family members see themselves and other family members of their patients
            my_memberships = FamilyMember.objects.filter(user=user)
            my_patients = my_memberships.values_list('patient_id', flat=True)
            return FamilyMember.objects.filter(patient_id__in=my_patients)
        else:
            # Doctors/Admin see all
            return FamilyMember.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return FamilyMemberListSerializer
        return FamilyMemberSerializer
    
    @action(detail=False, methods=['get'])
    def my_patients(self, request):
        """
        Get all patients the current family member monitors
        GET /api/v1/family/members/my_patients/
        """
        if request.user.user_type != 'FAMILY':
            return Response(
                {'error': 'Only family members can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        memberships = FamilyMember.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('patient__user')
        
        patients_data = []
        for membership in memberships:
            patients_data.append({
                'membership_id': membership.id,
                'patient_id': membership.patient.id,
                'patient_name': membership.patient.user.get_full_name(),
                'relationship': membership.get_relationship_display(),
                'access_level': membership.access_level,
                'is_primary_caregiver': membership.is_primary_caregiver,
                'last_viewed_at': membership.last_viewed_at
            })
        
        return Response(patients_data)
    
    @action(detail=True, methods=['post'])
    def update_permissions(self, request, pk=None):
        """
        Update family member permissions
        POST /api/v1/family/members/{id}/update_permissions/
        Body: {"can_view_vitals": true, "can_manage_medications": false}
        """
        member = self.get_object()
        
        # Only patient or admin can update permissions
        if request.user.user_type not in ['PATIENT', 'ADMIN']:
            if not (request.user.user_type == 'FAMILY' and 
                    FamilyMember.objects.filter(
                        user=request.user,
                        patient=member.patient,
                        can_invite_others=True
                    ).exists()):
                return Response(
                    {'error': 'You do not have permission to update permissions'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Update permissions
        permission_fields = [
            'can_view_vitals', 'can_view_medications', 'can_view_alerts',
            'can_view_medical_history', 'can_acknowledge_alerts',
            'can_add_notes', 'can_manage_medications', 'can_invite_others'
        ]
        
        for field in permission_fields:
            if field in request.data:
                setattr(member, field, request.data[field])
        
        member.save()
        
        serializer = FamilyMemberSerializer(member)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def record_view(self, request, pk=None):
        """
        Record that family member viewed patient data
        POST /api/v1/family/members/{id}/record_view/
        """
        member = self.get_object()
        
        # Only the family member themselves can record their view
        if member.user != request.user:
            return Response(
                {'error': 'Cannot record view for another user'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        member.record_view()
        
        return Response({'message': 'View recorded'})


class FamilyInvitationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing family invitations
    """
    serializer_class = FamilyInvitationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['patient', 'status']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return FamilyInvitation.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            # Can see invitations for patients they monitor
            my_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return FamilyInvitation.objects.filter(patient_id__in=my_patients)
        else:
            return FamilyInvitation.objects.all()
    
    @action(detail=False, methods=['post'])
    def send_invitation(self, request):
        """
        Send invitation to family member
        POST /api/v1/family/invitations/send_invitation/
        """
        serializer = SendInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        patient_id = request.data.get('patient_id')
        
        if not patient_id:
            return Response(
                {'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission to invite
        if request.user.user_type == 'PATIENT':
            if patient.user != request.user:
                return Response(
                    {'error': 'Cannot invite for another patient'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif request.user.user_type == 'FAMILY':
            # Check if they have permission to invite
            if not FamilyMember.objects.filter(
                user=request.user,
                patient=patient,
                can_invite_others=True
            ).exists():
                return Response(
                    {'error': 'You do not have permission to invite others'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Check if invitation already exists
        existing = FamilyInvitation.objects.filter(
            patient=patient,
            invitee_email=data['invitee_email'],
            status='PENDING'
        ).first()
        
        if existing:
            return Response(
                {'error': 'An invitation is already pending for this email'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create invitation
        invitation = FamilyInvitation.objects.create(
            patient=patient,
            invited_by=request.user,
            invitee_email=data['invitee_email'],
            invitee_phone=data.get('invitee_phone', ''),
            invitee_name=data.get('invitee_name', ''),
            relationship=data['relationship'],
            access_level=data.get('access_level', 'BASIC'),
            personal_message=data.get('personal_message', '')
        )
        
        # Send invitation email
        invitation_url = f"{settings.FRONTEND_URL}/family/accept-invitation/{invitation.invitation_token}"
        
        try:
            send_mail(
                subject=f"You've been invited to monitor {patient.user.get_full_name()}'s health",
                message=f"""
Hi {data.get('invitee_name', 'there')},

{request.user.get_full_name()} has invited you to help monitor the health of {patient.user.get_full_name()} through CarePAL.

{data.get('personal_message', '')}

To accept this invitation, please click the link below:
{invitation_url}

This invitation will expire in 7 days.

Best regards,
CarePAL Team
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[data['invitee_email']],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send invitation email: {str(e)}")
        
        output_serializer = FamilyInvitationSerializer(invitation)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def accept_invitation(self, request):
        """
        Accept family invitation
        POST /api/v1/family/invitations/accept_invitation/
        Body: {"invitation_token": "xxx"}
        """
        token = request.data.get('invitation_token')
        
        if not token:
            return Response(
                {'error': 'invitation_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            invitation = FamilyInvitation.objects.get(
                invitation_token=token,
                status='PENDING'
            )
        except FamilyInvitation.DoesNotExist:
            return Response(
                {'error': 'Invalid or expired invitation'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if invitation.is_expired:
            invitation.status = 'EXPIRED'
            invitation.save()
            return Response(
                {'error': 'This invitation has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user email matches invitation
        if request.user.email != invitation.invitee_email:
            return Response(
                {'error': 'This invitation was sent to a different email address'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create family member
        family_member, created = FamilyMember.objects.get_or_create(
            user=request.user,
            patient=invitation.patient,
            defaults={
                'relationship': invitation.relationship,
                'access_level': invitation.access_level,
                'invited_by': invitation.invited_by,
                'invitation_accepted_at': timezone.now()
            }
        )
        
        if not created:
            # Update if already exists
            family_member.is_active = True
            family_member.relationship = invitation.relationship
            family_member.access_level = invitation.access_level
            family_member.invitation_accepted_at = timezone.now()
            family_member.save()
        
        # Update invitation status
        invitation.status = 'ACCEPTED'
        invitation.accepted_at = timezone.now()
        invitation.accepted_by = request.user
        invitation.save()
        
        serializer = FamilyMemberSerializer(family_member)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel invitation
        POST /api/v1/family/invitations/{id}/cancel/
        """
        invitation = self.get_object()
        
        if invitation.status != 'PENDING':
            return Response(
                {'error': 'Can only cancel pending invitations'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        invitation.status = 'CANCELLED'
        invitation.save()
        
        return Response({'message': 'Invitation cancelled'})


class FamilyNoteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for family notes
    """
    serializer_class = FamilyNoteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'note_type', 'is_important', 'is_private']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'FAMILY':
            # Get patients this family member monitors
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            
            # See all non-private notes + own private notes
            return FamilyNote.objects.filter(
                Q(patient_id__in=my_patients, is_private=False) |
                Q(family_member__user=user)
            )
        elif user.user_type == 'PATIENT':
            return FamilyNote.objects.filter(patient__user=user)
        else:
            return FamilyNote.objects.all()
    
    def perform_create(self, serializer):
        # Get family member instance
        patient_id = self.request.data.get('patient')
        
        try:
            family_member = FamilyMember.objects.get(
                user=self.request.user,
                patient_id=patient_id,
                is_active=True
            )
        except FamilyMember.DoesNotExist:
            raise serializers.ValidationError('You are not a family member for this patient')
        
        if not family_member.can_add_notes:
            raise serializers.ValidationError('You do not have permission to add notes')
        
        serializer.save(family_member=family_member)


class FamilyCommunicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for family communications
    """
    serializer_class = FamilyCommunicationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'message_type', 'parent_message']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'FAMILY':
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return FamilyCommunication.objects.filter(patient_id__in=my_patients)
        elif user.user_type == 'PATIENT':
            return FamilyCommunication.objects.filter(patient__user=user)
        else:
            return FamilyCommunication.objects.all()
    
    def perform_create(self, serializer):
        patient_id = self.request.data.get('patient')
        
        try:
            family_member = FamilyMember.objects.get(
                user=self.request.user,
                patient_id=patient_id,
                is_active=True
            )
        except FamilyMember.DoesNotExist:
            raise serializers.ValidationError('You are not a family member for this patient')
        
        serializer.save(sender=family_member)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Mark message as read
        POST /api/v1/family/communications/{id}/mark_read/
        """
        message = self.get_object()
        
        # Get family member
        try:
            family_member = FamilyMember.objects.get(
                user=request.user,
                patient=message.patient,
                is_active=True
            )
        except FamilyMember.DoesNotExist:
            return Response(
                {'error': 'You are not a family member for this patient'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        message.mark_as_read(family_member.id)
        
        return Response({'message': 'Marked as read'})


class CareScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for care schedules
    """
    serializer_class = CareScheduleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'assigned_to', 'status', 'schedule_type']
    ordering = ['scheduled_date', 'scheduled_time']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'FAMILY':
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return CareSchedule.objects.filter(patient_id__in=my_patients)
        elif user.user_type == 'PATIENT':
            return CareSchedule.objects.filter(patient__user=user)
        else:
            return CareSchedule.objects.all()
    
    def perform_create(self, serializer):
        patient_id = self.request.data.get('patient')
        
        try:
            family_member = FamilyMember.objects.get(
                user=self.request.user,
                patient_id=patient_id,
                is_active=True
            )
        except FamilyMember.DoesNotExist:
            raise serializers.ValidationError('You are not a family member for this patient')
        
        serializer.save(created_by=family_member)
    
    @action(detail=True, methods=['post'])
    def mark_complete(self, request, pk=None):
        """
        Mark schedule as complete
        POST /api/v1/family/schedules/{id}/mark_complete/
        """
        schedule = self.get_object()
        
        if schedule.status in ['COMPLETED', 'CANCELLED']:
            return Response(
                {'error': 'Schedule is already completed or cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = MarkScheduleCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        schedule.status = 'COMPLETED'
        schedule.completed_at = timezone.now()
        schedule.completion_notes = serializer.validated_data.get('completion_notes', '')
        schedule.save()
        
        output_serializer = CareScheduleSerializer(schedule)
        return Response(output_serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming schedules
        GET /api/v1/family/schedules/upcoming/?patient_id=1&days=7
        """
        patient_id = request.query_params.get('patient_id')
        days = int(request.query_params.get('days', 7))
        
        queryset = self.get_queryset().filter(
            status='SCHEDULED',
            scheduled_date__gte=timezone.now().date(),
            scheduled_date__lte=timezone.now().date() + timedelta(days=days)
        )
        
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        serializer = CareScheduleSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        """
        Get schedules assigned to current user
        GET /api/v1/family/schedules/my_tasks/
        """
        if request.user.user_type != 'FAMILY':
            return Response(
                {'error': 'Only family members can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        my_memberships = FamilyMember.objects.filter(
            user=request.user,
            is_active=True
        )
        
        queryset = CareSchedule.objects.filter(
            assigned_to__in=my_memberships,
            status='SCHEDULED'
        ).order_by('scheduled_date', 'scheduled_time')
        
        serializer = CareScheduleSerializer(queryset, many=True)
        return Response(serializer.data)


class FamilyDashboardView(APIView):
    """
    Get family dashboard for a patient
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/v1/family/dashboard/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            return Response(
                {'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify access
        if request.user.user_type == 'FAMILY':
            try:
                family_member = FamilyMember.objects.get(
                    user=request.user,
                    patient_id=patient_id,
                    is_active=True
                )
            except FamilyMember.DoesNotExist:
                return Response(
                    {'error': 'You do not have access to this patient'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        try:
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get active alerts
        active_alerts = Alert.objects.filter(
            patient=patient,
            status__in=['PENDING', 'SENT', 'DELIVERED', 'ACKNOWLEDGED', 'ESCALATED']
        )
        
        # Get medication adherence rate (last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        adherence_records = MedicationAdherence.objects.filter(
            medication__patient=patient,
            scheduled_date__gte=seven_days_ago.date()
        )
        
        if adherence_records.exists():
            total = adherence_records.count()
            taken = adherence_records.filter(status='TAKEN').count()
            adherence_rate = (taken / total * 100) if total > 0 else 0
        else:
            adherence_rate = 0
        
        # Get recent vitals
        recent_vitals = {}
        vital_types = ['BP', 'HR', 'SPO2', 'TEMP']
        
        for vt_code in vital_types:
            latest = VitalReading.objects.filter(
                patient=patient,
                vital_type__code=vt_code
            ).order_by('-measured_at').first()
            
            if latest:
                recent_vitals[vt_code] = {
                    'value': latest.get_display_value(),
                    'measured_at': latest.measured_at,
                    'is_anomaly': latest.is_anomaly
                }
        
        # Get upcoming schedules
        upcoming = CareSchedule.objects.filter(
            patient=patient,
            status='SCHEDULED',
            scheduled_date__gte=timezone.now().date(),
            scheduled_date__lte=timezone.now().date() + timedelta(days=7)
        ).order_by('scheduled_date', 'scheduled_time')[:5]
        
        # Get unread messages
        if request.user.user_type == 'FAMILY':
            unread_count = FamilyCommunication.objects.filter(
                patient=patient
            ).exclude(
                read_by__contains=family_member.id
            ).count()
        else:
            unread_count = 0
        
        # Patient status
        if active_alerts.filter(severity='EMERGENCY').exists():
            patient_status = 'emergency'
        elif active_alerts.filter(severity='CRITICAL').exists():
            patient_status = 'critical'
        elif active_alerts.filter(severity='WARNING').exists():
            patient_status = 'warning'
        else:
            patient_status = 'stable'
        
        dashboard_data = {
            'patient_name': patient.user.get_full_name(),
            'patient_status': patient_status,
            'active_alerts_count': active_alerts.count(),
            'critical_alerts_count': active_alerts.filter(
                severity__in=['CRITICAL', 'EMERGENCY']
            ).count(),
            'medication_adherence_rate': round(adherence_rate, 2),
            'recent_vitals': recent_vitals,
            'upcoming_schedules': CareScheduleSerializer(upcoming, many=True).data,
            'unread_messages_count': unread_count
        }
        
        serializer = FamilyDashboardSerializer(dashboard_data)
        return Response(serializer.data)


class FamilyActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing activity logs
    """
    serializer_class = FamilyActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['family_member', 'patient', 'action']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'FAMILY':
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return FamilyActivityLog.objects.filter(patient_id__in=my_patients)
        elif user.user_type == 'PATIENT':
            return FamilyActivityLog.objects.filter(patient__user=user)
        else:
            return FamilyActivityLog.objects.all()
