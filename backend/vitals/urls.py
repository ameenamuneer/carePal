from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VitalTypeViewSet,
    DataSourceViewSet,
    VitalReadingViewSet,
    ContinuousVitalSessionViewSet,
    VitalTrendAnalysisViewSet,
    DashboardViewSet
)

app_name = 'vitals'

router = DefaultRouter()
router.register(r'vital-types', VitalTypeViewSet, basename='vital-type')
router.register(r'data-sources', DataSourceViewSet, basename='data-source')
router.register(r'readings', VitalReadingViewSet, basename='reading')
router.register(r'sessions', ContinuousVitalSessionViewSet, basename='session')
router.register(r'trends', VitalTrendAnalysisViewSet, basename='trend')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
