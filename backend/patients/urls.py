from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PatientProfileViewSet,
    EmergencyContactViewSet,
    HealthConditionViewSet
)

app_name = 'patients'

router = DefaultRouter()
router.register(r'profiles', PatientProfileViewSet, basename='patient-profile')
router.register(r'emergency-contacts', EmergencyContactViewSet, basename='emergency-contact')
router.register(r'health-conditions', HealthConditionViewSet, basename='health-condition')

urlpatterns = [
    path('', include(router.urls)),
]
