from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HealthMetricViewSet,
    TrendAnalysisViewSet,
    RiskScoreViewSet,
    InsightRecordViewSet,
    HealthReportViewSet,
    ScheduledReportViewSet,
    ReportTemplateViewSet,
    PatientDashboardView,
    FamilyDashboardView
)

app_name = 'analytics'

router = DefaultRouter()
router.register(r'metrics', HealthMetricViewSet, basename='health-metric')
router.register(r'trends', TrendAnalysisViewSet, basename='trend-analysis')
router.register(r'risk-scores', RiskScoreViewSet, basename='risk-score')
router.register(r'insights', InsightRecordViewSet, basename='insight-record')
router.register(r'reports', HealthReportViewSet, basename='health-report')
router.register(r'scheduled-reports', ScheduledReportViewSet, basename='scheduled-report')
router.register(r'templates', ReportTemplateViewSet, basename='report-template')

urlpatterns = [
    # Dashboards
    path('dashboard/patient/', PatientDashboardView.as_view(), name='patient-dashboard'),
    path('dashboard/family/', FamilyDashboardView.as_view(), name='family-dashboard'),
    
    # Router URLs
    path('', include(router.urls)),
]
