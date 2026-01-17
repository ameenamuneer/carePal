from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FamilyMemberViewSet,
    FamilyInvitationViewSet,
    FamilyNoteViewSet,
    FamilyCommunicationViewSet,
    CareScheduleViewSet,
    FamilyActivityLogViewSet,
    FamilyDashboardView
)

app_name = 'family'

router = DefaultRouter()
router.register(r'members', FamilyMemberViewSet, basename='family-member')
router.register(r'invitations', FamilyInvitationViewSet, basename='family-invitation')
router.register(r'notes', FamilyNoteViewSet, basename='family-note')
router.register(r'communications', FamilyCommunicationViewSet, basename='family-communication')
router.register(r'schedules', CareScheduleViewSet, basename='care-schedule')
router.register(r'activity-logs', FamilyActivityLogViewSet, basename='activity-log')

urlpatterns = [
    # Dashboard
    path('dashboard/', FamilyDashboardView.as_view(), name='family-dashboard'),
    
    # Router URLs
    path('', include(router.urls)),
]
