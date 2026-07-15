from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from django.http import FileResponse, Http404
import os

from .models import (
    HealthMetric, TrendAnalysis, RiskScore, InsightRecord,
    HealthReport, ScheduledReport, ReportTemplate, DashboardSnapshot
)
from .serializers import *
from patients.models import PatientProfile
from .tasks import (
    compute_health_metrics,
    generate_health_report,
    compute_risk_scores
)

import logging
logger = logging.getLogger(__name__)


class HealthMetricViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for health metrics (read-only, computed by Celery)
    """
    serializer_class = HealthMetricSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'period_type']
    ordering = ['-period_end']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return HealthMetric.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return HealthMetric.objects.filter(patient_id__in=my_patients)
        else:
            return HealthMetric.objects.all()
    
    @action(detail=False, methods=['post'])
    def compute_now(self, request):
        """
        Manually trigger metrics computation
        POST /api/v1/analytics/metrics/compute_now/
        """
        serializer = ComputeMetricsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Trigger Celery task
        task = compute_health_metrics.delay(
            patient_id=data['patient_id'],
            period_type=data['period_type'],
            start_date=str(data['start_date']),
            end_date=str(data['end_date'])
        )
        
        return Response({
            'message': 'Metrics computation started',
            'task_id': task.id,
            'patient_id': data['patient_id'],
            'period_type': data['period_type']
        }, status=status.HTTP_202_ACCEPTED)


class TrendAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for trend analysis
    """
    serializer_class = TrendAnalysisSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'analysis_type']
    ordering = ['-computed_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return TrendAnalysis.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return TrendAnalysis.objects.filter(patient_id__in=my_patients)
        else:
            return TrendAnalysis.objects.all()


class RiskScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for risk scores
    """
    serializer_class = RiskScoreSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'risk_type', 'risk_category', 'is_active']
    ordering = ['-computed_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return RiskScore.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return RiskScore.objects.filter(patient_id__in=my_patients)
        else:
            return RiskScore.objects.all()
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Get active risk scores for a patient
        GET /api/v1/analytics/risk-scores/active/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            return Response(
                {'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(
            patient_id=patient_id,
            is_active=True,
            valid_until__gte=timezone.now()
        )
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class InsightRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for insight records
    """
    serializer_class = InsightRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = [
        'patient', 'insight_type', 'insight_category',
        'validation_passed', 'requires_review'
    ]
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return InsightRecord.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return InsightRecord.objects.filter(patient_id__in=my_patients)
        else:
            return InsightRecord.objects.all()


class HealthReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for health reports
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['patient', 'report_type', 'status']
    ordering = ['-generated_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return HealthReport.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return HealthReport.objects.filter(patient_id__in=my_patients)
        else:
            return HealthReport.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return HealthReportListSerializer
        return HealthReportSerializer
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Generate a new health report
        POST /api/v1/analytics/reports/generate/
        """
        serializer = GenerateReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Create report record
        report = HealthReport.objects.create(
            patient_id=data['patient_id'],
            generated_by=request.user,
            report_type=data['report_type'],
            report_title=data.get('report_title', f"{data['report_type']} Report"),
            report_start_date=data['start_date'],
            report_end_date=data['end_date'],
            status='generating',
            ai_enhanced=data.get('include_ai_insights', True)
        )
        
        # Trigger report generation task
        generate_health_report.delay(
            report_id=report.id,
            include_ai_insights=data.get('include_ai_insights', True),
            generate_pdf=data.get('generate_pdf', True),
            generate_excel=data.get('generate_excel', False),
            template_id=data.get('template_id')
        )
        
        output_serializer = HealthReportSerializer(report)
        return Response(output_serializer.data, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """
        Download report as PDF
        GET /api/v1/analytics/reports/{id}/download_pdf/
        """
        report = self.get_object()
        
        if not report.pdf_file:
            return Response(
                {'error': 'PDF file not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update access tracking
        report.download_count += 1
        report.last_accessed_at = timezone.now()
        report.save(update_fields=['download_count', 'last_accessed_at'])
        
        # Serve file
        try:
            return FileResponse(
                report.pdf_file.open('rb'),
                content_type='application/pdf',
                as_attachment=True,
                filename=os.path.basename(report.pdf_file.name)
            )
        except Exception as e:
            logger.error(f"Error serving PDF: {str(e)}")
            raise Http404("PDF file not found")
    
    @action(detail=True, methods=['get'])
    def download_excel(self, request, pk=None):
        """
        Download report as Excel
        GET /api/v1/analytics/reports/{id}/download_excel/
        """
        report = self.get_object()
        
        if not report.excel_file:
            return Response(
                {'error': 'Excel file not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update access tracking
        report.download_count += 1
        report.last_accessed_at = timezone.now()
        report.save(update_fields=['download_count', 'last_accessed_at'])
        
        # Serve file
        try:
            return FileResponse(
                report.excel_file.open('rb'),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                filename=os.path.basename(report.excel_file.name)
            )
        except Exception as e:
            logger.error(f"Error serving Excel file: {str(e)}")
            raise Http404("Excel file not found")


class ScheduledReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for scheduled reports
    """
    serializer_class = ScheduledReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['patient', 'frequency', 'is_active']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'PATIENT':
            return ScheduledReport.objects.filter(patient__user=user)
        elif user.user_type == 'FAMILY':
            from family.models import FamilyMember
            my_patients = FamilyMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('patient_id', flat=True)
            return ScheduledReport.objects.filter(patient_id__in=my_patients)
        else:
            return ScheduledReport.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ReportTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for report templates
    """
    serializer_class = ReportTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['report_type', 'is_default', 'is_active']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        return ReportTemplate.objects.filter(is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PatientDashboardView(APIView):
    """
    Patient-specific dashboard with comprehensive health overview
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/v1/analytics/dashboard/patient/?patient_id=1
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
        
        # Check for cached snapshot
        cache_key = f"patient_dashboard_{patient_id}"
        snapshot = DashboardSnapshot.objects.filter(
            patient_id=patient_id,
            dashboard_type='patient',
            is_valid=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if snapshot:
            return Response(snapshot.snapshot_data)
        
        # Generate fresh dashboard data
        from .engines.metrics_engine import MetricsEngine
        from .insights.rule_based_insights import RuleBasedInsights
        
        try:
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get latest metrics (7 days)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)
        
        engine = MetricsEngine(patient)
        metrics = engine.compute_period_metrics(start_date, end_date)
        
        # Get insights
        insights_gen = RuleBasedInsights(patient)
        insights = insights_gen.generate_insights(metrics)
        
        # Get active risk scores
        risk_scores = RiskScore.objects.filter(
            patient=patient,
            is_active=True,
            valid_until__gte=timezone.now()
        )
        
        risk_assessment = {}
        for risk in risk_scores:
            risk_assessment[risk.risk_type] = {
                'score': float(risk.risk_score),
                'category': risk.risk_category,
                'factors': risk.risk_factors
            }
        
        dashboard_data = {
            'patient_id': patient.id,
            'patient_name': patient.user.get_full_name(),
            'health_score': {
                'score': metrics['overall']['health_score'],
                'category': self._get_health_category(metrics['overall']['health_score']),
                'trend': metrics['overall']['trend_direction']
            },
            'vitals_summary': metrics['vitals'],
            'medication_adherence': {
                'rate': float(metrics['medications']['adherence_rate']),
                'total_scheduled': metrics['medications']['total_scheduled'],
                'total_taken': metrics['medications']['total_taken'],
                'trend': metrics['medications'].get('trend', 'stable')
            },
            'alerts': {
                'total': metrics['alerts']['total'],
                'by_severity': metrics['alerts']['by_severity'],
                'avg_response_time': float(metrics['alerts']['avg_response_time_minutes']) if metrics['alerts']['avg_response_time_minutes'] else None
            },
            'risk_assessment': risk_assessment,
            'insights': [i['text'] for i in insights[:5]],
            'recommendations': [i['recommendation'] for i in insights[:5]],
            'data_completeness': float(metrics['overall']['data_completeness']),
            'last_updated': timezone.now().isoformat()
        }
        
        # Cache the dashboard
        DashboardSnapshot.objects.create(
            patient=patient,
            dashboard_type='patient',
            snapshot_data=dashboard_data
        )
        
        serializer = PatientDashboardSerializer(dashboard_data)
        return Response(serializer.data)
    
    def _get_health_category(self, score):
        """Determine health category from score"""
        if score >= 85:
            return 'excellent'
        elif score >= 70:
            return 'good'
        elif score >= 50:
            return 'fair'
        else:
            return 'poor'


_FAMILY_INSIGHT_PROMPT = """
You are CarePal's family insight writer. A family member is checking on their loved one's health today.
Your job is to write ONE short, warm, plain-English sentence for each card on their dashboard.

Rules:
- Write as if talking directly to a caring family member (not medical jargon)
- Be specific — name the medication, food, or vital type when you have it
- Be honest but calm: flag problems clearly without causing panic
- If something is genuinely good, say so warmly
- If no data exists for a category, say so simply
- Max 2 sentences per card. No bullet points. No markdown.
- Output ONLY valid JSON with exactly these keys:
  medications, nutrition, mood, vitals, activity

Example output:
{
  "medications": "All of today's medications were taken on time — great day!",
  "nutrition": "Lunch came in a bit late at 4 PM, and overall intake is a little low at 900 kcal.",
  "mood": "They reported feeling happy this morning, which is wonderful to hear.",
  "vitals": "Everything looks normal except temperature, which is slightly elevated at 38.2°C.",
  "activity": "A quiet day overall — they had a short walk and rested most of the afternoon."
}
"""


def _generate_family_insights(
    patient,
    today,
    adherence_today: list,
    taken: int,
    total: int,
    meals_today: list,
    today_kcal: int,
    calorie_target,
    nut_percent,
    mood_log,
    latest_vitals: list,
    active_alerts: list,
    all_activity_today: list,
) -> dict:
    """
    Call Gemini to generate one warm natural-language sentence per dashboard card.
    Falls back to structured defaults if the LLM call fails.
    """
    import json as _json
    import os

    # ── Build a rich text context ─────────────────────────────────────────────
    patient_name = patient.user.get_full_name() or 'the patient'

    # Medications section
    med_lines = []
    for a in adherence_today:
        time_str = a.scheduled_time.strftime('%I:%M %p') if a.scheduled_time else 'unknown time'
        actual_str = ''
        if a.actual_datetime:
            actual_str = f', taken at {a.actual_datetime.strftime("%I:%M %p")}'
        med_lines.append(
            f'  • {a.medication.medication_name} ({a.medication.dosage or ""})'
            f' scheduled {time_str}: {a.status}{actual_str}'
        )
    med_block = '\n'.join(med_lines) if med_lines else '  (no medications scheduled today)'

    # Nutrition section
    meal_lines = []
    for m in meals_today:
        meal_time = m.meal_time.strftime('%I:%M %p')
        meal_lines.append(
            f'  • {m.meal_type} at {meal_time}: {m.description} (~{m.estimated_kcal} kcal)'
        )
    nut_block = '\n'.join(meal_lines) if meal_lines else '  (no meals logged today)'
    target_str = f'{today_kcal} / {calorie_target} kcal ({nut_percent}% of target)' \
        if calorie_target else f'{today_kcal} kcal (no target set)'

    # Mood section
    if mood_log:
        details = mood_log.details or {}
        mood_block = (
            f'  Label: {details.get("mood_label", "unknown")}, '
            f'score: {details.get("mood_score", "unknown")}/10 '
            f'at {mood_log.observed_at.strftime("%I:%M %p")}'
        )
    else:
        mood_block = '  (no mood data today)'

    # Vitals section
    vitals_lines = []
    for v in latest_vitals:
        anomaly_flag = ' ⚠️ ANOMALY' if v['is_anomaly'] else ''
        vitals_lines.append(
            f'  • {v["type_name"]}: {v["value"]} {v["unit"]}'
            f' (measured {v["measured_at"][11:16]}){anomaly_flag}'
        )
    vitals_block = '\n'.join(vitals_lines) if vitals_lines else '  (no vitals recorded today)'

    # Alerts section
    alert_lines = [
        f'  • [{a["severity"]}] {a["title"]}: {a["message"]}'
        for a in active_alerts
    ]
    alerts_block = '\n'.join(alert_lines) if alert_lines else '  (no active alerts)'

    # Full activity log
    activity_lines = []
    for a in all_activity_today:
        activity_lines.append(
            f'  • [{a.observed_at.strftime("%I:%M %p")}] '
            f'{a.activity_type}: {a.description}'
        )
    activity_block = '\n'.join(activity_lines) if activity_lines else '  (no activity logged today)'

    context = f"""
Patient: {patient_name}
Date: {today}

=== MEDICATIONS ===
{med_block}

=== NUTRITION ===
Daily intake: {target_str}
{nut_block}

=== MOOD ===
{mood_block}

=== VITALS ===
{vitals_block}

=== ACTIVE ALERTS ===
{alerts_block}

=== FULL DAY ACTIVITY LOG ===
{activity_block}
"""

    # ── Gemini call ───────────────────────────────────────────────────────────
    try:
        from google import genai
        from django.conf import settings as django_settings

        api_key = (
            os.environ.get('GOOGLE_API_KEY')
            or getattr(django_settings, 'GOOGLE_API_KEY', None)
            or os.environ.get('GEMINI_API_KEY', '')
        )
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=context,
            config={
                'system_instruction': _FAMILY_INSIGHT_PROMPT,
                'temperature': 0.4,
            },
        )
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.rsplit('```', 1)[0]
        insights = _json.loads(raw.strip())
        # Ensure all expected keys are present
        for key in ('medications', 'nutrition', 'mood', 'vitals', 'activity'):
            if key not in insights:
                insights[key] = None
        return insights
    except Exception as e:
        logger.warning(f'[FamilyInsights] LLM call failed: {e}')
        # Graceful fallback — structured defaults so the UI still works
        return {
            'medications': (
                f'All {total} medications taken today.' if taken == total and total > 0
                else f'{taken} of {total} medications taken today.' if total > 0
                else 'No medications scheduled today.'
            ),
            'nutrition': (
                f'About {today_kcal} kcal consumed today'
                + (f' — {nut_percent}% of daily target.' if nut_percent else '.')
            ) if meals_today else 'No meals logged yet today.',
            'mood': (
                f'Mood logged: {(mood_log.details or {}).get("mood_label", "")}.'
                if mood_log else 'No mood data today.'
            ),
            'vitals': (
                'One or more vitals flagged as anomalous — please review.'
                if any(v['is_anomaly'] for v in latest_vitals)
                else 'Vitals look normal based on latest readings.'
                if latest_vitals else 'No vitals recorded today.'
            ),
            'activity': (
                f'{len(all_activity_today)} activities logged today.'
                if all_activity_today else 'No activity logged today.'
            ),
        }


class FamilyDashboardView(APIView):
    """
    Family-friendly dashboard: plain-English summaries of medication,
    nutrition, mood, vitals, and recent activity for one patient.
    GET /api/v1/analytics/dashboard/family/?patient_id=1
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_id = request.query_params.get('patient_id')
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Access guard
        if request.user.user_type == 'FAMILY':
            from family.models import FamilyMember
            if not FamilyMember.objects.filter(
                user=request.user, patient_id=patient_id, is_active=True
            ).exists():
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        elif request.user.user_type not in ('DOCTOR', 'ADMIN'):
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

        try:
            patient = PatientProfile.objects.select_related('user').get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        from medications.models import MedicationAdherence
        from agent.models import NutritionLog, PatientActivityLog
        from vitals.models import VitalReading
        from alerts.models import Alert

        # ── Medications ──────────────────────────────────────────────────────
        adherence_today = list(
            MedicationAdherence.objects.filter(
                medication__patient=patient, scheduled_date=today
            ).select_related('medication')
        )
        taken = sum(1 for a in adherence_today if a.status == 'TAKEN')
        total = len(adherence_today)
        if total == 0:
            med_status = 'none'
        elif taken == total:
            med_status = 'good'
        elif taken == 0:
            med_status = 'bad'
        else:
            med_status = 'partial'

        # ── Nutrition ─────────────────────────────────────────────────────────
        meals_today = list(
            NutritionLog.objects.filter(patient=patient, meal_time__gte=today_start)
            .order_by('meal_time')
        )
        today_kcal = sum(m.estimated_kcal or 0 for m in meals_today)
        target = patient.daily_calorie_target
        nut_percent = round(today_kcal * 100 / target) if target else None
        if not meals_today:
            nut_status = 'none'
        elif nut_percent is not None and nut_percent < 50:
            nut_status = 'low'
        elif nut_percent is not None and nut_percent >= 80:
            nut_status = 'good'
        else:
            nut_status = 'ok'

        # ── Mood (from activity logs) ─────────────────────────────────────────
        mood_log = (
            PatientActivityLog.objects.filter(
                patient=patient, activity_type='MOOD', observed_at__gte=today_start
            ).order_by('-observed_at').first()
        )
        mood_data = None
        if mood_log:
            details = mood_log.details or {}
            mood_data = {
                'label': details.get('mood_label', ''),
                'score': details.get('mood_score'),
                'observed_at': mood_log.observed_at.isoformat(),
            }

        # ── Latest vitals (one per type) ──────────────────────────────────────
        vitals_qs = (
            VitalReading.objects.filter(patient=patient, is_deleted=False)
            .select_related('vital_type')
            .order_by('vital_type_id', '-measured_at')
        )
        seen = set()
        latest_vitals = []
        for v in vitals_qs[:50]:
            if v.vital_type_id not in seen:
                seen.add(v.vital_type_id)
                latest_vitals.append({
                    'type_name': v.vital_type.name,
                    'value': str(v.value),
                    'unit': v.unit or '',
                    'measured_at': v.measured_at.isoformat(),
                    'is_anomaly': v.is_anomaly,
                })

        # ── Active alerts ─────────────────────────────────────────────────────
        active_alerts = list(
            Alert.objects.filter(
                patient=patient,
                status__in=['PENDING', 'SENT', 'DELIVERED'],
            ).select_related('alert_type').order_by('-created_at')[:10]
        )
        alert_counts = {
            'warning': sum(1 for a in active_alerts if a.severity == 'WARNING'),
            'critical': sum(1 for a in active_alerts if a.severity in ('CRITICAL', 'EMERGENCY')),
            'info': sum(1 for a in active_alerts if a.severity == 'INFO'),
        }
        alerts_list = [
            {
                'id': a.id,
                'title': a.title,
                'message': a.message,
                'severity': a.severity,
                'category': a.alert_type.category,
                'created_at': a.created_at.isoformat(),
            }
            for a in active_alerts
        ]

        # ── All today's activity logs (full context for LLM) ─────────────────
        all_activity_today = list(
            PatientActivityLog.objects.filter(
                patient=patient, observed_at__gte=today_start
            ).order_by('observed_at')
        )
        recent_activity = all_activity_today[-5:]
        activity_list = [
            {
                'activity_type': a.activity_type,
                'description': a.description,
                'observed_at': a.observed_at.isoformat(),
            }
            for a in recent_activity
        ]

        # ── AI insights ───────────────────────────────────────────────────────
        ai_insights = _generate_family_insights(
            patient=patient,
            today=today,
            adherence_today=adherence_today,
            taken=taken,
            total=total,
            meals_today=meals_today,
            today_kcal=today_kcal,
            calorie_target=target,
            nut_percent=nut_percent,
            mood_log=mood_log,
            latest_vitals=latest_vitals,
            active_alerts=active_alerts,
            all_activity_today=all_activity_today,
        )

        return Response({
            'patient_id': patient.id,
            'patient_name': patient.user.get_full_name(),
            'generated_at': timezone.now().isoformat(),
            'ai_insights': ai_insights,
            'medications': {
                'today_taken': taken,
                'today_total': total,
                'status': med_status,
            },
            'nutrition': {
                'today_kcal': today_kcal,
                'daily_target': target,
                'today_percent': nut_percent,
                'status': nut_status,
                'meal_count': len(meals_today),
            },
            'mood': mood_data,
            'vitals': latest_vitals,
            'alerts': alerts_list,
            'alert_counts': alert_counts,
            'recent_activity': activity_list,
        })


class DoctorDashboardView(APIView):
    """
    Clinical dashboard for doctors: adherence trends, nutrition trends,
    active alerts, vitals, and 7-day charts.
    GET /api/v1/analytics/dashboard/doctor/?patient_id=1
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_id = request.query_params.get('patient_id')
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Access guard — doctors only (or admin)
        if request.user.user_type == 'DOCTOR':
            from users.models import ClinicalRelationship
            if not ClinicalRelationship.objects.filter(
                doctor=request.user, patient_id=patient_id, is_active=True
            ).exists():
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        elif request.user.user_type not in ('ADMIN',):
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

        try:
            patient = PatientProfile.objects.select_related('user').get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=6)

        from medications.models import Medication, MedicationAdherence
        from django.db.models import Count, Q, Sum
        from agent.models import NutritionLog, PatientActivityLog
        from agent.nutrition_utils import get_consecutive_low_days
        from vitals.models import VitalReading
        from alerts.models import Alert

        # ── Medications today ────────────────────────────────────────────────
        adherence_today = list(
            MedicationAdherence.objects.filter(
                medication__patient=patient, scheduled_date=today
            ).select_related('medication')
        )
        taken_today = sum(1 for a in adherence_today if a.status == 'TAKEN')
        total_today = len(adherence_today)
        active_meds = Medication.objects.filter(patient=patient, status='ACTIVE').count()

        # ── 7-day adherence trend ─────────────────────────────────────────────
        adherence_7day_qs = (
            MedicationAdherence.objects.filter(
                medication__patient=patient,
                scheduled_date__gte=week_ago,
                scheduled_date__lte=today,
            )
            .values('scheduled_date')
            .annotate(
                total=Count('id'),
                taken=Count('id', filter=Q(status='TAKEN')),
                missed=Count('id', filter=Q(status='MISSED')),
            )
            .order_by('scheduled_date')
        )
        adherence_7day = [
            {
                'date': str(r['scheduled_date']),
                'taken': r['taken'],
                'total': r['total'],
                'missed': r['missed'],
                'rate': round(r['taken'] / r['total'] * 100) if r['total'] else 0,
            }
            for r in adherence_7day_qs
        ]
        week_taken = sum(r['taken'] for r in adherence_7day)
        week_total = sum(r['total'] for r in adherence_7day)
        week_rate = round(week_taken / week_total * 100) if week_total else 0

        # Missed meds today
        missed_today = [
            {
                'medication_name': a.medication.medication_name,
                'scheduled_time': a.scheduled_time.strftime('%H:%M') if a.scheduled_time else None,
                'status': a.status,
            }
            for a in adherence_today if a.status in ('MISSED', 'SKIPPED')
        ]

        # ── Nutrition today & 7-day trend ─────────────────────────────────────
        meals_today = list(
            NutritionLog.objects.filter(patient=patient, meal_time__gte=today_start)
            .order_by('meal_time')
        )
        today_kcal = sum(m.estimated_kcal or 0 for m in meals_today)
        target = patient.daily_calorie_target
        nut_percent = round(today_kcal * 100 / target) if target else None
        consecutive_low = get_consecutive_low_days(patient, today, window=7)

        nutrition_7day_qs = (
            NutritionLog.objects.filter(
                patient=patient,
                meal_time__date__gte=week_ago,
                meal_time__date__lte=today,
            )
            .values('meal_time__date')
            .annotate(total_kcal=Sum('estimated_kcal'), meal_count=Count('id'))
            .order_by('meal_time__date')
        )
        nutrition_7day = [
            {
                'date': str(r['meal_time__date']),
                'kcal': r['total_kcal'] or 0,
                'meal_count': r['meal_count'],
                'below_target': (r['total_kcal'] or 0) < (target or 9999),
            }
            for r in nutrition_7day_qs
        ]
        meals_today_list = [
            {
                'meal_type': m.meal_type,
                'estimated_kcal': m.estimated_kcal,
                'description': m.description,
                'meal_time': m.meal_time.isoformat(),
                'appetite': m.appetite,
            }
            for m in meals_today
        ]

        # ── Vitals (latest per type) ───────────────────────────────────────────
        vitals_qs = (
            VitalReading.objects.filter(patient=patient, is_deleted=False)
            .select_related('vital_type')
            .order_by('vital_type_id', '-measured_at')
        )
        seen = set()
        latest_vitals = []
        for v in vitals_qs[:50]:
            if v.vital_type_id not in seen:
                seen.add(v.vital_type_id)
                latest_vitals.append({
                    'type_name': v.vital_type.name,
                    'value': str(v.value),
                    'unit': v.unit or '',
                    'measured_at': v.measured_at.isoformat(),
                    'is_anomaly': v.is_anomaly,
                    'anomaly_severity': v.anomaly_severity,
                })

        # ── Active alerts ─────────────────────────────────────────────────────
        active_alerts = list(
            Alert.objects.filter(
                patient=patient,
                status__in=['PENDING', 'SENT', 'DELIVERED'],
            ).select_related('alert_type').order_by('-created_at')[:20]
        )
        alerts_list = [
            {
                'id': a.id,
                'title': a.title,
                'message': a.message,
                'severity': a.severity,
                'category': a.alert_type.category,
                'code': a.alert_type.code,
                'created_at': a.created_at.isoformat(),
            }
            for a in active_alerts
        ]

        return Response({
            'patient_id': patient.id,
            'patient_name': patient.user.get_full_name(),
            'generated_at': timezone.now().isoformat(),
            'medications': {
                'today_taken': taken_today,
                'today_total': total_today,
                'today_rate': round(taken_today / total_today * 100) if total_today else None,
                'week_rate': week_rate,
                'active_count': active_meds,
                'missed_today': missed_today,
                'adherence_7day': adherence_7day,
            },
            'nutrition': {
                'today_kcal': today_kcal,
                'daily_target': target,
                'today_percent': nut_percent,
                'consecutive_low_days': consecutive_low,
                'meals_today': meals_today_list,
                'nutrition_7day': nutrition_7day,
            },
            'vitals': latest_vitals,
            'alerts': alerts_list,
            'alert_counts': {
                'warning': sum(1 for a in active_alerts if a.severity == 'WARNING'),
                'critical': sum(1 for a in active_alerts if a.severity in ('CRITICAL', 'EMERGENCY')),
                'info': sum(1 for a in active_alerts if a.severity == 'INFO'),
            },
        })
