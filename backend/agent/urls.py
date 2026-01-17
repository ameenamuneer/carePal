from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AgentSessionViewSet

router = DefaultRouter()
router.register(r'sessions', AgentSessionViewSet, basename='agent-session')

urlpatterns = [
    path('', include(router.urls)),
]
