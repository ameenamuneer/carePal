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


class FamilyDashboardView(APIView):
    """
    Family-specific dashboard with patient overview
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/v1/analytics/dashboard/family/?patient_id=1
        """
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            return Response(
                {'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify family access
        if request.user.user_type == 'FAMILY':
            from family.models import FamilyMember
            try:
                FamilyMember.objects.get(
                    user=request.user,
                    patient_id=patient_id,
                    is_active=True
                )
            except FamilyMember.DoesNotExist:
                return Response(
                    {'error': 'Access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Similar to patient dashboard but family-focused
        # Implementation similar to PatientDashboardView
        # (Abbreviated for brevity)
        
        return Response({
            'message': 'Family dashboard - implementation continues'
        })
