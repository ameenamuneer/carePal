from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MedicationViewSet,
    MedicationScheduleViewSet,
    MedicationAdherenceViewSet,
    MedicationRefillViewSet,
    MedicationInteractionViewSet,
    MedicationAdherencePatternViewSet
)

app_name = 'medications'

router = DefaultRouter()
router.register(r'medications', MedicationViewSet, basename='medication')
router.register(r'schedules', MedicationScheduleViewSet, basename='schedule')
router.register(r'adherence', MedicationAdherenceViewSet, basename='adherence')
router.register(r'refills', MedicationRefillViewSet, basename='refill')
router.register(r'interactions', MedicationInteractionViewSet, basename='interaction')
router.register(r'patterns', MedicationAdherencePatternViewSet, basename='pattern')

urlpatterns = [
    path('', include(router.urls)),
]
