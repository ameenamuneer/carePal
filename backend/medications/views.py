from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta
import logging

from .models import (
    Medication, MedicationSchedule, MedicationAdherence,
    MedicationRefill, MedicationInteraction, MedicationAdherencePattern
)
from .serializers import (
    MedicationListSerializer, MedicationDetailSerializer,
    MedicationCreateUpdateSerializer, MedicationScheduleSerializer,
    MedicationAdherenceDetailSerializer, TodaysMedicationScheduleSerializer,
    AdherenceRateSerializer,
    MedicationRefillSerializer, MedicationInteractionSerializer,
    MedicationAdherencePatternSerializer
)
from patients.models import PatientProfile

logger = logging.getLogger(__name__)


class MedicationViewSet(viewsets.ModelViewSet):
    """
    Complete medication management endpoint
    Handles all medication CRUD operations
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'form', 'route', 'is_critical']
    search_fields = ['medication_name', 'generic_name', 'purpose']
    ordering_fields = ['created_at', 'medication_name', 'start_date']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter medications based on user type"""
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return Medication.objects.filter(
                patient__user=user
            ).select_related('patient__user')
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return Medication.objects.filter(
                patient_id__in=linked_patients
            ).select_related('patient__user')
        else:
            # Healthcare provider or admin
            return Medication.objects.all().select_related('patient__user')
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return MedicationListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return MedicationCreateUpdateSerializer
        return MedicationDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """Create medication and generate adherence records"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        medication = serializer.save()
        
        # Trigger adherence record generation
        from .tasks import generate_adherence_records
        generate_adherence_records.delay(medication.id, days=30)
        
        # Return detailed view
        output_serializer = MedicationDetailSerializer(medication)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update medication and regenerate schedules if needed"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        medication = serializer.save()
        
        # Regenerate adherence if schedules changed
        if 'schedules' in request.data:
            from .tasks import regenerate_adherence_records
            regenerate_adherence_records.delay(medication.id)
        
        output_serializer = MedicationDetailSerializer(medication)
        return Response(output_serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Get all active medications for patient
        GET /api/v1/medications/medications/active/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id and request.user.user_type == 'PATIENT':
            patient = PatientProfile.objects.filter(user=request.user).first()
            patient_id = patient.id if patient else None
        
        if not patient_id:
            return Response(
                {'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        medications = self.get_queryset().filter(
            patient_id=patient_id,
            status='ACTIVE'
        ).prefetch_related('schedules')
        
        serializer = MedicationListSerializer(medications, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def needs_refill(self, request):
        """
        Get medications that need refill
        GET /api/v1/medications/medications/needs_refill/
        """
        queryset = self.get_queryset().filter(status='ACTIVE')
        medications_needing_refill = [med for med in queryset if med.needs_refill]
        
        serializer = MedicationListSerializer(medications_needing_refill, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def discontinue(self, request, pk=None):
        """
        Discontinue a medication
        POST /api/v1/medications/medications/{id}/discontinue/
        Body: {"reason": "Side effects"}
        """
        medication = self.get_object()
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response(
                {'error': 'Discontinuation reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        medication.status = 'DISCONTINUED'
        medication.discontinuation_reason = reason
        medication.discontinued_by = request.user
        medication.discontinued_at = timezone.now()
        medication.save()
        
        # Cancel future scheduled doses
        MedicationAdherence.objects.filter(
            medication=medication,
            status='SCHEDULED',
            scheduled_datetime__gte=timezone.now()
        ).update(status='SKIPPED', skip_reason='Medication discontinued')
        
        serializer = MedicationDetailSerializer(medication)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """
        Resume a discontinued medication
        POST /api/v1/medications/medications/{id}/resume/
        """
        medication = self.get_object()
        
        if medication.status not in ['DISCONTINUED', 'ON_HOLD']:
            return Response(
                {'error': 'Only discontinued or on-hold medications can be resumed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        medication.status = 'ACTIVE'
        medication.save()
        
        # Generate new adherence records
        from .tasks import generate_adherence_records
        generate_adherence_records.delay(medication.id, days=30)
        
        serializer = MedicationDetailSerializer(medication)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def adherence_summary(self, request, pk=None):
        """
        Get adherence summary for a medication
        GET /api/v1/medications/medications/{id}/adherence_summary/?days=7
        """
        medication = self.get_object()
        days = int(request.query_params.get('days', 7))
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        records = MedicationAdherence.objects.filter(
            medication=medication,
            scheduled_datetime__gte=start_date,
            scheduled_datetime__lte=end_date
        )
        
        total = records.count()
        taken = records.filter(status='TAKEN').count()
        missed = records.filter(status='MISSED').count()
        skipped = records.filter(status='SKIPPED').count()
        
        adherence_rate = round((taken / total * 100), 1) if total > 0 else 0
        completion_rate = round(((taken + skipped) / total * 100), 1) if total > 0 else 0
        
        return Response({
            'medication_id': medication.id,
            'medication_name': medication.medication_name,
            'period_days': days,
            'start_date': start_date.date(),
            'end_date': end_date.date(),
            'total_scheduled': total,
            'total_taken': taken,
            'total_missed': missed,
            'total_skipped': skipped,
            'adherence_rate': adherence_rate,
            'completion_rate': completion_rate
        })


class MedicationAdherenceViewSet(viewsets.ModelViewSet):
    """
    Medication adherence tracking endpoint
    Handles marking medications as taken/skipped/missed
    """
    serializer_class = MedicationAdherenceDetailSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['medication', 'status', 'scheduled_date']
    ordering_fields = ['scheduled_datetime']
    ordering = ['-scheduled_datetime']
    
    def get_queryset(self):
        """Filter adherence records based on user type"""
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return MedicationAdherence.objects.filter(
                medication__patient__user=user
            ).select_related('medication', 'schedule')
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return MedicationAdherence.objects.filter(
                medication__patient_id__in=linked_patients
            ).select_related('medication', 'schedule')
        else:
            return MedicationAdherence.objects.all().select_related('medication', 'schedule')
    
    @action(detail=True, methods=['post'])
    def mark_taken(self, request, pk=None):
        """
        Mark medication as taken
        POST /api/v1/medications/adherence/{id}/mark_taken/
        Body: {"confirmation_method": "app", "notes": "Taken with breakfast"}
        """
        adherence = self.get_object()
        
        if adherence.status == 'TAKEN':
            return Response(
                {'message': 'Medication already marked as taken'},
                status=status.HTTP_200_OK
            )
        
        adherence.status = 'TAKEN'
        adherence.actual_datetime = timezone.now()
        adherence.confirmed_by_patient = True
        adherence.confirmation_method = request.data.get('confirmation_method', 'app')
        adherence.notes = request.data.get('notes', '')
        adherence.save()
        
        # Update medication quantity
        if adherence.medication.quantity_remaining and adherence.medication.quantity_remaining > 0:
            adherence.medication.quantity_remaining -= 1
            adherence.medication.save()
        
        serializer = self.get_serializer(adherence)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_skipped(self, request, pk=None):
        """
        Mark medication as skipped
        POST /api/v1/medications/adherence/{id}/mark_skipped/
        Body: {"skip_reason": "Feeling nauseous"}
        """
        adherence = self.get_object()
        
        skip_reason = request.data.get('skip_reason', '')
        if not skip_reason:
            return Response(
                {'error': 'Skip reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        adherence.status = 'SKIPPED'
        adherence.skip_reason = skip_reason
        adherence.notes = request.data.get('notes', '')
        adherence.save()
        
        serializer = self.get_serializer(adherence)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """
        Get today's complete medication schedule
        GET /api/v1/medications/adherence/today/?patient_id=1
        
        Returns a complete schedule for today with all medications
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id and request.user.user_type == 'PATIENT':
            patient = PatientProfile.objects.filter(user=request.user).first()
            patient_id = patient.id if patient else None
        
        if not patient_id:
            return Response(
                {'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        today = timezone.now().date()
        
        # Get all adherence records for today
        adherence_records = MedicationAdherence.objects.filter(
            medication__patient_id=patient_id,
            scheduled_date=today
        ).select_related('medication', 'schedule').order_by('scheduled_time')
        
        # Build schedule data
        schedule_data = []
        for record in adherence_records:
            schedule_data.append({
                'adherence_id': record.id,
                'medication_id': record.medication.id,
                'medication_name': record.medication.medication_name,
                'dosage': record.medication.dosage,
                'form': record.medication.form,
                'instructions': record.medication.instructions or '',
                'scheduled_time': record.scheduled_time,
                'time_label': record.schedule.time_label if record.schedule else '',
                'with_food': record.schedule.with_food if record.schedule else False,
                'special_instructions': record.schedule.special_instructions if record.schedule else '',
                'is_critical': record.medication.is_critical,
                'status': record.status,
                'actual_datetime': record.actual_datetime,
                'notes': record.notes or '',
                'is_overdue': record.is_overdue
            })
        
        serializer = TodaysMedicationScheduleSerializer(schedule_data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming medication doses
        GET /api/v1/medications/adherence/upcoming/?hours=4
        """
        hours = int(request.query_params.get('hours', 4))
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id and request.user.user_type == 'PATIENT':
            patient = PatientProfile.objects.filter(user=request.user).first()
            patient_id = patient.id if patient else None
        
        now = timezone.now()
        until = now + timedelta(hours=hours)
        
        upcoming = self.get_queryset().filter(
            medication__patient_id=patient_id,
            status='SCHEDULED',
            scheduled_datetime__gte=now,
            scheduled_datetime__lte=until
        ).order_by('scheduled_datetime')
        
        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def rate(self, request):
        """
        Get adherence rate for a period
        GET /api/v1/medications/adherence/rate/?days=7&patient_id=1
        """
        days = int(request.query_params.get('days', 7))
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id and request.user.user_type == 'PATIENT':
            patient = PatientProfile.objects.filter(user=request.user).first()
            patient_id = patient.id if patient else None
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        records = self.get_queryset().filter(
            medication__patient_id=patient_id,
            scheduled_datetime__gte=start_date,
            scheduled_datetime__lte=end_date
        )
        
        total = records.count()
        taken = records.filter(status='TAKEN').count()
        missed = records.filter(status='MISSED').count()
        skipped = records.filter(status='SKIPPED').count()
        
        adherence_rate = round((taken / total * 100), 1) if total > 0 else 0
        completion_rate = round(((taken + skipped) / total * 100), 1) if total > 0 else 0
        
        data = {
            'period_days': days,
            'start_date': start_date.date(),
            'end_date': end_date.date(),
            'total_scheduled': total,
            'total_taken': taken,
            'total_missed': missed,
            'total_skipped': skipped,
            'adherence_rate': adherence_rate,
            'completion_rate': completion_rate
        }
        
        serializer = AdherenceRateSerializer(data)
        return Response(serializer.data)


class MedicationScheduleViewSet(viewsets.ModelViewSet):
    """
    Medication schedule management
    Handles time-based medication scheduling
    """
    serializer_class = MedicationScheduleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return MedicationSchedule.objects.filter(medication__patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return MedicationSchedule.objects.filter(
                medication__patient_id__in=linked_patients
            )
        else:
            return MedicationSchedule.objects.all()


# ==========================================
# Legacy/Auxiliary ViewSets (Preserved)
# ==========================================

class MedicationRefillViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing refill requests
    """
    serializer_class = MedicationRefillSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['medication', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return MedicationRefill.objects.filter(medication__patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return MedicationRefill.objects.filter(
                medication__patient_id__in=linked_patients
            )
        else:
            return MedicationRefill.objects.all()
    
    def create(self, request, *args, **kwargs):
        """Create refill request"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        medication_id = serializer.validated_data['medication'].id
        medication = Medication.objects.get(id=medication_id)
        
        # Check if refills are available
        if medication.refills_remaining <= 0:
            return Response(
                {'error': 'No refills remaining. Please contact your doctor.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refill = serializer.save(requested_by=request.user)
        
        output_serializer = MedicationRefillSerializer(refill)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve refill request (admin/doctor only)
        POST /api/v1/medications/refills/{id}/approve/
        """
        if request.user.user_type not in ['DOCTOR', 'ADMIN']:
            return Response(
                {'error': 'Only doctors or admins can approve refills'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        refill = self.get_object()
        
        refill.status = 'APPROVED'
        refill.approved_by = request.user
        refill.approved_at = timezone.now()
        refill.save()
        
        # Decrement refills remaining
        medication = refill.medication
        medication.refills_remaining -= 1
        medication.save()
        
        serializer = MedicationRefillSerializer(refill)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_filled(self, request, pk=None):
        """
        Mark refill as filled
        POST /api/v1/medications/refills/{id}/mark_filled/
        Body: {"filled_date": "2025-01-18"}
        """
        refill = self.get_object()
        
        filled_date = request.data.get('filled_date', timezone.now().date())
        
        refill.status = 'FILLED'
        refill.filled_date = filled_date
        refill.save()
        
        # Update medication quantity
        if refill.medication.quantity_prescribed:
            refill.medication.quantity_remaining = refill.medication.quantity_prescribed
            refill.medication.save()
        
        serializer = MedicationRefillSerializer(refill)
        return Response(serializer.data)


class MedicationInteractionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing drug interactions
    """
    serializer_class = MedicationInteractionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['severity', 'is_active']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return MedicationInteraction.objects.filter(
                Q(medication_1__patient__user=user) | 
                Q(medication_2__patient__user=user),
                is_active=True
            )
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return MedicationInteraction.objects.filter(
                Q(medication_1__patient_id__in=linked_patients) | 
                Q(medication_2__patient_id__in=linked_patients),
                is_active=True
            )
        else:
            return MedicationInteraction.objects.filter(is_active=True)
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """
        Acknowledge interaction (doctor/admin only)
        POST /api/v1/medications/interactions/{id}/acknowledge/
        Body: {"override_reason": "Benefits outweigh risks"}
        """
        if request.user.user_type not in ['DOCTOR', 'ADMIN']:
            return Response(
                {'error': 'Only doctors or admins can acknowledge interactions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        interaction = self.get_object()
        override_reason = request.data.get('override_reason', '')
        
        interaction.acknowledged_by = request.user
        interaction.acknowledged_at = timezone.now()
        interaction.override_reason = override_reason
        interaction.save()
        
        serializer = MedicationInteractionSerializer(interaction)
        return Response(serializer.data)


class MedicationAdherencePatternViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing adherence patterns (read-only, computed by background tasks)
    """
    serializer_class = MedicationAdherencePatternSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['patient', 'medication', 'period_label']
    ordering = ['-period_end']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return MedicationAdherencePattern.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return MedicationAdherencePattern.objects.filter(
                patient_id__in=linked_patients
            )
        else:
            return MedicationAdherencePattern.objects.all()
