from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AgentSessionViewSet, PatientActivityLogViewSet

router = DefaultRouter()
router.register(r'sessions', AgentSessionViewSet, basename='agent-session')
router.register(r'activity-logs', PatientActivityLogViewSet, basename='activity-log')

urlpatterns = [
    path('', include(router.urls)),
]
