from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlertViewSet, AlertTypeViewSet, AlertRuleViewSet,
    NotificationPreferenceViewSet, AlertDeliveryViewSet,
    AlertStatisticsViewSet, AlertDashboardView
)

router = DefaultRouter()
router.register(r'alerts', AlertViewSet, basename='alert')
router.register(r'types', AlertTypeViewSet)
router.register(r'rules', AlertRuleViewSet, basename='alert-rule')
router.register(r'preferences', NotificationPreferenceViewSet, basename='notification-preference')
router.register(r'deliveries', AlertDeliveryViewSet, basename='alert-delivery')
router.register(r'statistics', AlertStatisticsViewSet, basename='alert-statistics')

urlpatterns = [
    path('dashboard/', AlertDashboardView.as_view(), name='alert-dashboard'),
    path('', include(router.urls)),
]
