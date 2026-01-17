from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CloudProviderViewSet,
    CloudAPICredentialViewSet,
    BluetoothDeviceViewSet,
    DeviceSyncLogViewSet,
    DataConflictViewSet,
    FitbitOAuthView,
    FitbitOAuthCallbackView,
    GoogleFitOAuthView,
    GoogleFitOAuthCallbackView,
    DeviceStatusView
)

app_name = 'devices'

router = DefaultRouter()
router.register(r'cloud-providers', CloudProviderViewSet, basename='cloud-provider')
router.register(r'cloud-credentials', CloudAPICredentialViewSet, basename='cloud-credential')
router.register(r'bluetooth', BluetoothDeviceViewSet, basename='bluetooth')
router.register(r'sync-logs', DeviceSyncLogViewSet, basename='sync-log')
router.register(r'conflicts', DataConflictViewSet, basename='conflict')

urlpatterns = [
    # OAuth endpoints
    path('cloud/fitbit/authorize/', FitbitOAuthView.as_view(), name='fitbit-authorize'),
    path('cloud/fitbit/callback/', FitbitOAuthCallbackView.as_view(), name='fitbit-callback'),
    path('cloud/google-fit/authorize/', GoogleFitOAuthView.as_view(), name='google-fit-authorize'),
    path('cloud/google-fit/callback/', GoogleFitOAuthCallbackView.as_view(), name='google-fit-callback'),
    
    # Device status
    path('status/', DeviceStatusView.as_view(), name='device-status'),
    
    # Router URLs
    path('', include(router.urls)),
]
