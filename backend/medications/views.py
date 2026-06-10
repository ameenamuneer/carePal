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
    Medication, MedicationAdherence,
    MedicationRefill, MedicationInteraction, MedicationAdherencePattern
)
from .serializers import (
    MedicationListSerializer, MedicationDetailSerializer,
    MedicationCreateUpdateSerializer,
    MedicationAdherenceDetailSerializer, TodaysMedicationScheduleSerializer,
    AdherenceRateSerializer,
    MedicationRefillSerializer, MedicationInteractionSerializer,
    MedicationAdherencePatternSerializer
)
from patients.models import PatientProfile
from ekacare.authentication import EkaCareAuth, EkaCareAPIException
from django.db import transaction

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
        """Filter medications based on user type and per-account permissions."""
        user = self.request.user

        if user.user_type == 'PATIENT':
            return Medication.objects.filter(
                patient__user=user
            ).select_related('patient__user')

        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            # Family can view medication schedule only (no editing)
            linked_patients = FamilyMember.objects.filter(
                user=user, is_active=True, can_view_medications=True
            ).values_list('patient_id', flat=True)
            return Medication.objects.filter(
                patient_id__in=linked_patients
            ).select_related('patient__user')

        elif user.user_type == 'DOCTOR':
            from users.models import ClinicalRelationship
            linked_patients = ClinicalRelationship.objects.filter(
                doctor=user, is_active=True, can_view_medications=True
            ).values_list('patient_id', flat=True)
            return Medication.objects.filter(
                patient_id__in=linked_patients
            ).select_related('patient__user')

        else:
            # ADMIN
            return Medication.objects.all().select_related('patient__user')
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return MedicationListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return MedicationCreateUpdateSerializer
        return MedicationDetailSerializer
    
    def _check_edit_permission(self, request):
        """Return a 403 Response if the user cannot edit medications, else None."""
        user = request.user
        if user.user_type == 'FAMILY':
            return Response(
                {'detail': 'Family members cannot modify medications.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.user_type == 'DOCTOR':
            # Check per-relationship permission for the patient being targeted
            patient_id = request.data.get('patient') or request.query_params.get('patient_id')
            if patient_id:
                from users.models import ClinicalRelationship
                allowed = ClinicalRelationship.objects.filter(
                    doctor=user, patient_id=patient_id,
                    is_active=True, can_edit_medications=True
                ).exists()
                if not allowed:
                    return Response(
                        {'detail': 'You do not have edit-medication permission for this patient.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        return None

    def create(self, request, *args, **kwargs):
        """
        Create medication and generate initial records

        Simplified: Just create today + next 7 days
        Midnight task will handle future days
        """
        err = self._check_edit_permission(request)
        if err:
            return err
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        medication = serializer.save()
        # No pre-generation — adherence records are created lazily when a date is first queried.
        logger.info(f"[MEDICATION] Created {medication.medication_name} (ID: {medication.id})")
        
        output_serializer = MedicationDetailSerializer(medication)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update medication and regenerate schedules if needed"""
        err = self._check_edit_permission(request)
        if err:
            return err
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

    def destroy(self, request, *args, **kwargs):
        """Delete medication — blocked for Family accounts."""
        err = self._check_edit_permission(request)
        if err:
            return err
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def check_duplicate(self, request):
        """
        Lightweight duplicate check before creating a medication.
        POST /api/v1/medications/medications/check_duplicate/
        Body: {medication_name, dosage, frequency, patient}
        Returns: {matches: [...], has_duplicate: bool}
        """
        name = request.data.get('medication_name', '').strip().lower()
        patient_id = request.data.get('patient')
        dosage = request.data.get('dosage', '').strip().lower()
        frequency = request.data.get('frequency', '')

        if not name or not patient_id:
            return Response({'matches': [], 'has_duplicate': False})

        # Find active meds for this patient with similar names
        existing = Medication.objects.filter(
            patient_id=patient_id,
            status='ACTIVE',
        )

        matches = []
        for med in existing:
            med_name_lower = med.medication_name.lower()
            # Direct substring match (catches "meftal" vs "meftal forte")
            if name in med_name_lower or med_name_lower in name:
                matches.append({
                    'id': med.id,
                    'medication_name': med.medication_name,
                    'dosage': med.dosage,
                    'frequency': med.frequency,
                    'status': med.status,
                    'same_dosage': med.dosage.lower() == dosage,
                    'same_frequency': med.frequency == frequency,
                })

        return Response({
            'matches': matches,
            'has_duplicate': len(matches) > 0,
        })

    @action(detail=False, methods=['post'])
    def import_prescription(self, request):
        """
        Import prescription - USES EKA PATIENT ID
        """
        try:
            prescription_id = request.data.get('prescription_id')
            patient = request.user.patient_profile
            
            # Ensure patient exists in Eka.Care
            if not patient.has_eka_patient:
                return Response(
                    {'error': 'Patient not registered in Eka.Care. Create patient first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Fetch prescription from Eka.Care
            eka_prescription = EkaCareAuth.make_request(
                'GET',
                f'/dr/v1/prescription/{prescription_id}'
            )
            
            # Verify patient match
            prescription_patient_id = eka_prescription.get('patient_id')
            prescription_partner_id = eka_prescription.get('partner_patient_id')
            
            # Match by either eka_patient_id or partner_patient_id
            if (prescription_patient_id != patient.eka_patient_id and 
                prescription_partner_id != patient.partner_patient_id):
                return Response(
                    {'error': 'Prescription does not belong to this patient'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Import and store medications
            medications = self._import_and_store_medications(
                eka_prescription,
                patient,
                prescription_id
            )
            
            serializer = MedicationListSerializer(medications, many=True)
            
            return Response({
                'success': True,
                'medications': serializer.data,
                'count': len(medications)
            }, status=status.HTTP_201_CREATED)
            
        except EkaCareAPIException as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    def _import_and_store_medications(
        self, 
        eka_prescription, 
        patient, 
        prescription_id
    ):
        """
        Transform Eka.Care prescription data and store in CarePAL DB
        """
        medications = []
        time_map = {
            'MORN': '08:00:00',
            'AFT': '14:00:00',
            'EVE': '18:00:00',
            'NIGHT': '21:00:00'
        }
        
        with transaction.atomic():
            for detail in eka_prescription.get('prescription_details', []):
                # Only process medication requests
                if detail.get('resource_type') != 'medicationrequest':
                    continue
                
                med_name = detail.get('med_name')
                if not med_name:
                    continue
                
                # Extract data
                dosage = detail.get('dose', {})
                duration = detail.get('duration', {})
                instructions = detail.get('dosage_instruction', {})
                
                # Create Medication in CarePAL DB
                medication = Medication.objects.create(
                    patient=patient,
                    medication_name=med_name,
                    generic_name=detail.get('generic_name', ''),
                    dosage=str(dosage.get('value', 1)) + ' ' + dosage.get('unit', 'tablet'),
                    form='TABLET',  # Defaulting
                    route='ORAL',   # Default
                    frequency='ONCE_DAILY', # Simplified default
                    times_per_day=duration.get('frequency', 1),
                    start_date=timezone.now().date(),
                    duration_days=duration.get('value', 0),
                    instructions=detail.get('note', ''),
                    status='ACTIVE',
                    
                    # Track Eka.Care source
                    source='EKA_CARE',
                    eka_prescription_id=prescription_id,
                    eka_drug_id=detail.get('partner_drug_id'),
                    eka_imported_at=timezone.now(),
                    
                    # Store full metadata
                    metadata={
                        'eka_prescription': prescription_id,
                        'eka_drug_id': detail.get('partner_drug_id'),
                        'snomed_id': detail.get('snomed_id'),
                        'custom_dosage': dosage.get('custom'),
                        'imported_at': timezone.now().isoformat()
                    }
                )
                
                # Set dose_times from Eka prescription timing data
                eka_times = instructions.get('when', [])
                if eka_times:
                    label_map = {'morning': 'Morning', 'afternoon': 'Afternoon', 'evening': 'Evening', 'night': 'Night'}
                    medication.dose_times = [
                        {'time': time_map.get(tk, '08:00'), 'label': label_map.get(tk, tk.capitalize())}
                        for tk in eka_times
                    ]
                    medication.save(update_fields=['dose_times'])
                
                medications.append(medication)
        
        return medications
    
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
        Get today's schedule — dynamically calculated from active medications.
        GET /api/v1/medications/adherence/today/?patient_id=1
        Delegates to the generic `schedule` action with date=today.
        """
        request.query_params._mutable = True  # allow patching for delegation
        request.query_params.setdefault('date', str(timezone.now().date()))
        request.query_params._mutable = False
        return self.schedule(request)

    @action(detail=False, methods=['get'])
    def schedule(self, request):
        """
        Dynamically calculate the medication schedule for any date.
        GET /api/v1/medications/adherence/schedule/?patient_id=1&date=2026-06-10

        - date defaults to today
        - For today or past dates: ensures MedicationAdherence rows exist (lazy creation)
          and returns actual status (TAKEN / MISSED / SCHEDULED).
        - For future dates: returns the calculated schedule with status='SCHEDULED'
          but does NOT create adherence rows yet.
        Past adherence rows are never modified — only new gaps are filled.
        """
        from .schedule_utils import get_schedule_for_date, ensure_adherence_records

        patient_id = request.query_params.get('patient_id')
        if not patient_id and request.user.user_type == 'PATIENT':
            patient = PatientProfile.objects.filter(user=request.user).first()
            patient_id = patient.id if patient else None

        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        date_str = request.query_params.get('date', str(timezone.now().date()))
        try:
            from datetime import date as date_type
            target_date = date_type.fromisoformat(date_str)
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.now().date()

        if target_date <= today:
            # Lazily ensure all adherence rows exist for this date, then return with real statuses
            pairs = ensure_adherence_records(int(patient_id), target_date)
            schedule_data = []
            for item, record in pairs:
                schedule_data.append({
                    'adherence_id': record.id,
                    'medication_id': item['medication_id'],
                    'medication_name': item['medication_name'],
                    'dosage': item['dosage'],
                    'form': item['form'],
                    'instructions': item['instructions'],
                    'scheduled_time': item['scheduled_time'],
                    'time_label': item['time_label'],
                    'with_food': False,
                    'special_instructions': '',
                    'is_critical': item['is_critical'],
                    'status': record.status,
                    'actual_datetime': record.actual_datetime,
                    'notes': record.notes or '',
                    'is_overdue': record.is_overdue,
                })
        else:
            # Future date — pure calculation, no DB writes
            items = get_schedule_for_date(int(patient_id), target_date)
            schedule_data = []
            for item in items:
                schedule_data.append({
                    'adherence_id': None,
                    'medication_id': item['medication_id'],
                    'medication_name': item['medication_name'],
                    'dosage': item['dosage'],
                    'form': item['form'],
                    'instructions': item['instructions'],
                    'scheduled_time': item['scheduled_time'],
                    'time_label': item['time_label'],
                    'with_food': False,
                    'special_instructions': '',
                    'is_critical': item['is_critical'],
                    'status': 'SCHEDULED',
                    'actual_datetime': None,
                    'notes': '',
                    'is_overdue': False,
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

    @action(detail=False, methods=['get'])
    def calendar_summary(self, request):
        """
        Return per-day adherence summary for calendar colouring.
        GET /api/v1/medications/adherence/calendar_summary/?patient_id=1&months_back=2

        Response: { "YYYY-MM-DD": { total, taken, missed, skipped, scheduled } }
        Only covers today and past dates — future dates are coloured client-side.
        """
        from datetime import date as date_type

        patient_id = request.query_params.get('patient_id')
        if not patient_id and request.user.user_type == 'PATIENT':
            patient = PatientProfile.objects.filter(user=request.user).first()
            patient_id = patient.id if patient else None

        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        months_back = int(request.query_params.get('months_back', 2))
        today = timezone.now().date()
        start_date = today - timedelta(days=months_back * 30)

        rows = (
            MedicationAdherence.objects
            .filter(
                medication__patient_id=patient_id,
                scheduled_date__gte=start_date,
                scheduled_date__lte=today,
            )
            .values('scheduled_date')
            .annotate(
                total=Count('id'),
                taken=Count('id', filter=Q(status='TAKEN')),
                missed=Count('id', filter=Q(status='MISSED')),
                skipped=Count('id', filter=Q(status='SKIPPED')),
                scheduled=Count('id', filter=Q(status='SCHEDULED')),
            )
        )

        result = {
            str(r['scheduled_date']): {
                'total': r['total'],
                'taken': r['taken'],
                'missed': r['missed'],
                'skipped': r['skipped'],
                'scheduled': r['scheduled'],
            }
            for r in rows
        }
        return Response(result)


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


class AIAgentMedicationViewSet(viewsets.ViewSet):
    """
    🤖 AI AGENT SPECIALIZED ENDPOINTS
    
    These endpoints are optimized for AI agent interaction:
    - Single calls return complete context
    - Include suggested actions
    - Minimal round-trips
    - Natural language friendly
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def check_now(self, request):
        """
        🤖 PRIMARY AI AGENT ENDPOINT
        
        GET /api/v1/ai-medications/check_now/?patient_id=1
        
        Returns everything AI needs in one call:
        - Upcoming medications (next 2 hours)
        - Overdue medications (past but not taken)
        - Recently taken (last 4 hours)
        - Today's summary
        - Suggested action
        
        AI agent calls this:
        - At start of every conversation
        - Every 15-30 minutes during waking hours
        - When patient asks about medications
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            # Try to get from authenticated user
            if request.user.user_type == 'PATIENT':
                patient = PatientProfile.objects.filter(user=request.user).first()
                patient_id = patient.id if patient else None
        
        if not patient_id:
            return Response(
                {'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        now = timezone.now()
        today = now.date()
        
        # ========== UPCOMING (Next 2 hours) ==========
        upcoming = MedicationAdherence.objects.filter(
            medication__patient_id=patient_id,
            status='SCHEDULED',
            scheduled_datetime__gte=now,
            scheduled_datetime__lte=now + timedelta(hours=2)
        ).select_related('medication', 'schedule').order_by('scheduled_datetime')
        
        # ========== OVERDUE (Should have been taken) ==========
        # Using computed property - no need to update DB
        overdue = MedicationAdherence.objects.filter(
            medication__patient_id=patient_id,
            status='SCHEDULED',
            scheduled_datetime__lt=now - timedelta(hours=1),  # 1 hour grace
            scheduled_datetime__gte=now - timedelta(hours=4)  # Last 4 hours only
        ).select_related('medication', 'schedule').order_by('scheduled_datetime')
        
        # ========== RECENTLY TAKEN ==========
        recently_taken = MedicationAdherence.objects.filter(
            medication__patient_id=patient_id,
            status='TAKEN',
            actual_datetime__gte=now - timedelta(hours=4)
        ).select_related('medication', 'schedule').order_by('-actual_datetime')
        
        # ========== TODAY'S SUMMARY ==========
        today_all = MedicationAdherence.objects.filter(
            medication__patient_id=patient_id,
            scheduled_date=today
        )
        
        total_today = today_all.count()
        taken_today = today_all.filter(status='TAKEN').count()
        missed_today = today_all.filter(status='MISSED').count()
        remaining_today = today_all.filter(status='SCHEDULED').count()
        
        # ========== SUGGESTED ACTION ==========
        suggested_action = self._compute_ai_suggestion(upcoming, overdue)
        
        # ========== BUILD RESPONSE ==========
        return Response({
            'timestamp': now.isoformat(),
            'patient_id': int(patient_id),
            
            # Critical data for AI agent
            'upcoming': self._serialize_adherence_minimal(upcoming),
            'overdue': self._serialize_adherence_minimal(overdue),
            'recently_taken': self._serialize_adherence_minimal(recently_taken),
            
            # Context
            'today_summary': {
                'total': total_today,
                'taken': taken_today,
                'missed': missed_today,
                'remaining': remaining_today,
                'completion_rate': round((taken_today / total_today * 100), 1) if total_today > 0 else 0
            },
            
            # AI action guidance
            'needs_attention': overdue.filter(medication__is_critical=True).exists(),
            'suggested_action': suggested_action,
            
            # Conversation starters for AI
            'conversation_prompts': self._generate_prompts(
                upcoming, overdue, taken_today, total_today
            )
        })
    
    def _serialize_adherence_minimal(self, queryset):
        """Minimal serialization optimized for AI agent"""
        return [
            {
                'adherence_id': adh.id,
                'medication_id': adh.medication.id,
                'medication_name': adh.medication.medication_name,
                'dosage': adh.medication.dosage,
                'form': adh.medication.form,
                'scheduled_time': adh.scheduled_time.strftime('%H:%M'),
                'scheduled_datetime': adh.scheduled_datetime.isoformat(),
                'time_label': '',
                'is_critical': adh.medication.is_critical,
                'with_food': False,
                'status': adh.status,
                'actual_datetime': adh.actual_datetime.isoformat() if adh.actual_datetime else None
            }
            for adh in queryset
        ]
    
    def _compute_ai_suggestion(self, upcoming, overdue):
        """What should AI agent do right now?"""
        now = timezone.now()
        
        # Priority 1: Critical overdue medications
        critical_overdue = overdue.filter(medication__is_critical=True)
        if critical_overdue.exists():
            return {
                'priority': 'CRITICAL',
                'action': 'REMIND_CRITICAL_OVERDUE',
                'urgency': 'high',
                'medications': [
                    {
                        'name': m.medication.medication_name,
                        'scheduled_time': m.scheduled_time.strftime('%H:%M'),
                        'adherence_id': m.id
                    }
                    for m in critical_overdue
                ],
                'suggested_message': f"I notice you haven't taken your {critical_overdue.first().medication.medication_name}. This is an important medication. Have you taken it?"
            }
        
        # Priority 2: Regular overdue medications
        if overdue.exists():
            return {
                'priority': 'HIGH',
                'action': 'REMIND_OVERDUE',
                'urgency': 'medium',
                'medications': [
                    {
                        'name': m.medication.medication_name,
                        'scheduled_time': m.scheduled_time.strftime('%H:%M'),
                        'adherence_id': m.id
                    }
                    for m in overdue
                ],
                'suggested_message': f"You have {overdue.count()} medication(s) that need to be taken. Would you like me to remind you?"
            }
        
        # Priority 3: Upcoming medications (within 15 minutes)
        if upcoming.exists():
            next_med = upcoming.first()
            minutes_until = int((next_med.scheduled_datetime - now).total_seconds() / 60)
            
            if minutes_until <= 15:
                return {
                    'priority': 'MEDIUM',
                    'action': 'PRE_REMIND',
                    'urgency': 'low',
                    'medication': {
                        'name': next_med.medication.medication_name,
                        'scheduled_time': next_med.scheduled_time.strftime('%H:%M'),
                        'minutes_until': minutes_until,
                        'adherence_id': next_med.id
                    },
                    'suggested_message': f"In {minutes_until} minutes, it will be time to take your {next_med.medication.medication_name}."
                }
        
        # Priority 4: All good
        return {
            'priority': 'LOW',
            'action': 'NONE',
            'urgency': 'none',
            'suggested_message': 'All medications are on track. Great job!'
        }
    
    def _generate_prompts(self, upcoming, overdue, taken_today, total_today):
        """Generate conversation starter prompts for AI"""
        prompts = []
        
        if overdue.exists():
            prompts.append(f"I notice you have {overdue.count()} medication(s) to take. Is everything okay?")
        
        if taken_today > 0 and total_today > 0:
            rate = round((taken_today / total_today * 100), 1)
            if rate == 100:
                prompts.append("You've taken all your medications today! Excellent work!")
            elif rate >= 80:
                prompts.append(f"You're doing well with your medications today - {rate}% complete!")
        
        if upcoming.exists():
            next_med = upcoming.first()
            prompts.append(f"Your next medication is {next_med.medication.medication_name} at {next_med.scheduled_time.strftime('%H:%M')}.")
        
        return prompts[:3]  # Return top 3 prompts
    
    @action(detail=False, methods=['post'])
    def mark_status(self, request):
        """
        🤖 AI AGENT STATUS UPDATE ENDPOINT
        
        POST /api/v1/ai-medications/mark_status/
        {
            "adherence_id": 123,
            "status": "TAKEN",  # or "MISSED", "SKIPPED"
            "reason": "Patient confirmed via voice",
            "timestamp": "2026-01-26T14:30:00Z"  # optional
        }
        
        Returns: Updated adherence record
        """
        adherence_id = request.data.get('adherence_id')
        new_status = request.data.get('status')
        reason = request.data.get('reason', '')
        timestamp_str = request.data.get('timestamp')
        
        # Validate
        if not adherence_id or not new_status:
            return Response(
                {'error': 'adherence_id and status are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_status not in ['TAKEN', 'MISSED', 'SKIPPED']:
            return Response(
                {'error': 'status must be TAKEN, MISSED, or SKIPPED'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            adherence = MedicationAdherence.objects.select_related('medication').get(
                id=adherence_id
            )
            
            # Update status
            adherence.status = new_status
            
            # Handle timestamp
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except:
                    timestamp = timezone.now()
            else:
                timestamp = timezone.now()
            
            # Status-specific updates
            if new_status == 'TAKEN':
                adherence.actual_datetime = timestamp
                adherence.confirmed_by_patient = True
                adherence.confirmation_method = 'ai_agent'
                adherence.notes = reason or 'Confirmed via AI agent'
                
                # Update medication quantity
                if adherence.medication.quantity_remaining:
                    adherence.medication.quantity_remaining = max(
                        0, adherence.medication.quantity_remaining - 1
                    )
                    adherence.medication.save()
                    
            elif new_status == 'SKIPPED':
                adherence.skip_reason = reason or 'Skipped via AI agent'
                adherence.notes = reason
                
            elif new_status == 'MISSED':
                adherence.miss_reason = reason or 'Marked as missed by AI agent'
                adherence.notes = reason
            
            adherence.save()
            
            logger.info(
                f"[AI-AGENT] Marked adherence {adherence_id} as {new_status} "
                f"for {adherence.medication.medication_name}"
            )
            
            return Response({
                'success': True,
                'adherence_id': adherence_id,
                'medication_name': adherence.medication.medication_name,
                'status': new_status,
                'timestamp': timestamp.isoformat(),
                'quantity_remaining': adherence.medication.quantity_remaining
            })
            
        except MedicationAdherence.DoesNotExist:
            return Response(
                {'error': f'Adherence record {adherence_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def patient_context(self, request):
        """
        🤖 AI AGENT CONTEXT ENDPOINT
        
        GET /api/v1/ai-medications/patient_context/?patient_id=1
        
        Returns complete patient medication context for AI conversations:
        - All active medications with full details
        - 7-day adherence summary
        - Critical medications list
        - Current adherence rate and performance
        
        AI agent calls this:
        - At start of conversation
        - When patient asks about their medications
        - When generating health reports
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
        
        # Active medications
        medications = Medication.objects.filter(
            patient_id=patient_id,
            status='ACTIVE'
        ).prefetch_related('schedules')
        
        # 7-day adherence calculation
        from .tasks import ai_compute_adherence_summary
        adherence_summary = ai_compute_adherence_summary(patient_id, days=7)
        
        # Critical medications
        critical_meds = medications.filter(is_critical=True)
        
        return Response({
            'patient_id': int(patient_id),
            'timestamp': timezone.now().isoformat(),
            
            # Medications
            'active_medications': [
                {
                    'id': med.id,
                    'name': med.medication_name,
                    'dosage': med.dosage,
                    'form': med.form,
                    'frequency': med.frequency,
                    'purpose': med.purpose,
                    'is_critical': med.is_critical,
                    'instructions': med.instructions,
                    'dose_times': med.dose_times,
                }
                for med in medications
            ],
            
            # Adherence summary
            'adherence_summary': adherence_summary or {
                'total': 0,
                'rate': 0,
                'performance': 'no_data'
            },
            
            # Critical info
            'critical_medications': [
                {
                    'name': med.medication_name,
                    'dosage': med.dosage,
                    'purpose': med.purpose
                }
                for med in critical_meds
            ],
            
            # Stats
            'stats': {
                'total_active': medications.count(),
                'total_critical': critical_meds.count(),
                'total_doses_per_day': sum(
                    len(med.dose_times) for med in medications
                )
            }
        })
    
    @action(detail=False, methods=['post'])
    def batch_mark_missed(self, request):
        """
        🤖 BATCH UPDATE ENDPOINT
        
        POST /api/v1/ai-medications/batch_mark_missed/
        {
            "adherence_ids": [123, 124, 125],
            "reason": "AI agent detected overdue after grace period"
        }
        
        Efficiently marks multiple medications as missed in one call
        """
        adherence_ids = request.data.get('adherence_ids', [])
        reason = request.data.get('reason', 'Marked as missed by AI agent')
        
        if not adherence_ids:
            return Response(
                {'error': 'adherence_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Batch update
        updated = MedicationAdherence.objects.filter(
            id__in=adherence_ids,
            status='SCHEDULED'
        ).update(
            status='MISSED',
            miss_reason=reason
        )
        
        logger.info(f"[AI-AGENT] Batch marked {updated} medications as missed")
        
        return Response({
            'success': True,
            'updated_count': updated,
            'adherence_ids': adherence_ids
        })
