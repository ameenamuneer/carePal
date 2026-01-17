from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta, time
from .models import (
    Medication, MedicationSchedule, MedicationAdherence,
    MedicationEscalation, MedicationInteraction, MedicationRefill,
    MedicationAdherencePattern
)
from .serializers import *
from patients.models import PatientProfile


class MedicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing medications
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['patient', 'status', 'form', 'route', 'is_critical']
    search_fields = ['medication_name', 'generic_name', 'brand_name', 'prescribed_by']
    ordering_fields = ['start_date', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return Medication.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return Medication.objects.filter(patient_id__in=linked_patients)
        else:
            return Medication.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MedicationListSerializer
        elif self.action == 'create':
            return MedicationCreateSerializer
        return MedicationSerializer
    
    def create(self, request, *args, **kwargs):
        """Create medication with schedules"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        medication = serializer.save()
        
        # Check for interactions with existing medications
        self._check_drug_interactions(medication)
        
        # Generate adherence records for the next 30 days
        from .tasks import generate_adherence_records
        generate_adherence_records.delay(medication.id, days=30)
        
        output_serializer = MedicationSerializer(medication)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update medication"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = MedicationSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        medication = serializer.save()
        
        # Regenerate adherence records if schedule changed
        if 'schedules' in request.data or 'start_date' in request.data or 'end_date' in request.data:
            from .tasks import regenerate_adherence_records
            regenerate_adherence_records.delay(medication.id)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def discontinue(self, request, pk=None):
        """
        Discontinue a medication
        POST /api/v1/medications/medications/{id}/discontinue/
        Body: {"reason": "Side effects too severe"}
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
        
        # Cancel future adherence records
        MedicationAdherence.objects.filter(
            medication=medication,
            status='SCHEDULED',
            scheduled_datetime__gte=timezone.now()
        ).update(status='SKIPPED', skip_reason='Medication discontinued')
        
        serializer = MedicationSerializer(medication)
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
        
        serializer = MedicationSerializer(medication)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Get all active medications for patient
        GET /api/v1/medications/medications/active/?patient_id=1
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
        
        medications = self.get_queryset().filter(
            patient_id=patient_id,
            status='ACTIVE'
        )
        
        serializer = MedicationSerializer(medications, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def needs_refill(self, request):
        """
        Get medications that need refill
        GET /api/v1/medications/medications/needs_refill/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        queryset = self.get_queryset().filter(status='ACTIVE')
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        medications_needing_refill = [med for med in queryset if med.needs_refill]
        
        serializer = MedicationSerializer(medications_needing_refill, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def adherence_summary(self, request, pk=None):
        """
        Get adherence summary for a medication
        GET /api/v1/medications/medications/{id}/adherence_summary/?period=7days
        """
        medication = self.get_object()
        period = request.query_params.get('period', '7days')
        
        # Calculate date range
        end_date = timezone.now()
        if period == '7days':
            start_date = end_date - timedelta(days=7)
        elif period == '30days':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)
        
        # Get adherence records
        records = MedicationAdherence.objects.filter(
            medication=medication,
            scheduled_datetime__gte=start_date,
            scheduled_datetime__lte=end_date
        )
        
        total = records.count()
        taken = records.filter(status='TAKEN').count()
        missed = records.filter(status='MISSED').count()
        skipped = records.filter(status='SKIPPED').count()
        
        adherence_rate = (taken / total * 100) if total > 0 else 0
        
        return Response({
            'medication_id': medication.id,
            'medication_name': medication.medication_name,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'total_scheduled': total,
            'total_taken': taken,
            'total_missed': missed,
            'total_skipped': skipped,
            'adherence_rate': round(adherence_rate, 2)
        })
    
    def _check_drug_interactions(self, new_medication):
        """Check for drug interactions with existing medications"""
        # Get other active medications for the same patient
        other_meds = Medication.objects.filter(
            patient=new_medication.patient,
            status='ACTIVE'
        ).exclude(id=new_medication.id)
        
        # This is simplified - in production, you'd check against a drug interaction database
        # For now, just check if there are known interactions in the medication's interactions field
        for other_med in other_meds:
            if other_med.medication_name in new_medication.interactions:
                # Create interaction record
                MedicationInteraction.objects.get_or_create(
                    medication_1=new_medication,
                    medication_2=other_med,
                    defaults={
                        'severity': 'MODERATE',
                        'description': f'Potential interaction between {new_medication.medication_name} and {other_med.medication_name}',
                        'clinical_effects': 'Please consult healthcare provider',
                        'management': 'Monitor patient closely'
                    }
                )


class MedicationScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing medication schedules
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


class MedicationAdherenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing adherence records
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['medication', 'status', 'scheduled_date']
    ordering_fields = ['scheduled_datetime']
    ordering = ['-scheduled_datetime']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return MedicationAdherence.objects.filter(medication__patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            linked_patients = FamilyMember.objects.filter(
                user=user
            ).values_list('patient_id', flat=True)
            return MedicationAdherence.objects.filter(
                medication__patient_id__in=linked_patients
            )
        else:
            return MedicationAdherence.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return MedicationAdherenceUpdateSerializer
        return MedicationAdherenceSerializer
    
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
        if adherence.medication.quantity_remaining:
            adherence.medication.quantity_remaining -= 1
            adherence.medication.save()
        
        serializer = MedicationAdherenceSerializer(adherence)
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
        adherence.save()
        
        serializer = MedicationAdherenceSerializer(adherence)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """
        Get today's medication schedule
        GET /api/v1/medications/adherence/today/?patient_id=1
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
        
        today = timezone.now().date()
        
        adherence_records = MedicationAdherence.objects.filter(
            medication__patient_id=patient_id,
            scheduled_date=today
        ).select_related('medication', 'schedule').order_by('scheduled_time')
        
        # Build daily schedule
        schedule_data = []
        for record in adherence_records:
            schedule_data.append({
                'medication_id': record.medication.id,
                'medication_name': record.medication.medication_name,
                'dosage': record.medication.dosage,
                'form': record.medication.form,
                'instructions': record.medication.instructions,
                'is_critical': record.medication.is_critical,
                'scheduled_time': record.scheduled_time,
                'time_label': record.schedule.time_label if record.schedule else '',
                'with_food': record.schedule.with_food if record.schedule else False,
                'adherence_id': record.id,
                'status': record.status,
                'actual_datetime': record.actual_datetime,
                'is_overdue': record.is_overdue
            })
        
        serializer = DailyMedicationScheduleSerializer(schedule_data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming medication doses
        GET /api/v1/medications/adherence/upcoming/?patient_id=1&hours=4
        """
        patient_id = request.query_params.get('patient_id')
        hours = int(request.query_params.get('hours', 4))
        
        if not patient_id:
            if request.user.user_type == 'PATIENT':
                patient = PatientProfile.objects.filter(user=request.user).first()
                patient_id = patient.id if patient else None
        
        now = timezone.now()
        until = now + timedelta(hours=hours)
        
        upcoming = MedicationAdherence.objects.filter(
            medication__patient_id=patient_id,
            status='SCHEDULED',
            scheduled_datetime__gte=now,
            scheduled_datetime__lte=until
        ).select_related('medication').order_by('scheduled_datetime')
        
        serializer = MedicationAdherenceSerializer(upcoming, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get overdue medications
        GET /api/v1/medications/adherence/overdue/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            if request.user.user_type == 'PATIENT':
                patient = PatientProfile.objects.filter(user=request.user).first()
                patient_id = patient.id if patient else None
        
        overdue = MedicationAdherence.objects.filter(
            medication__patient_id=patient_id,
            status='SCHEDULED',
            scheduled_datetime__lt=timezone.now()
        ).select_related('medication').order_by('scheduled_datetime')
        
        serializer = MedicationAdherenceSerializer(overdue, many=True)
        return Response(serializer.data)


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
