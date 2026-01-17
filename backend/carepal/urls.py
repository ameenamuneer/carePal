from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="CarePAL API",
        default_version='v1',
        description="CarePAL Bedside Health Assistant API Documentation",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('users.urls')),
    path('api/v1/patients/', include('patients.urls')),
    
    # Existing Apps - integrated for future use
    # path('api/patients/', include('patients.urls')),
    path('api/v1/vitals/', include('vitals.urls')),
    path('api/v1/medications/', include('medications.urls')),
    path('api/v1/devices/', include('devices.urls')),
    path('api/vitals/', include('vitals.urls')),
    path('api/agent/', include('agent.urls')),
    
    path('api/v1/alerts/', include('alerts.urls')),
    path('api/v1/family/', include('family.urls')),
    path('api/v1/analytics/', include('analytics.urls')),
    
    # Swagger Documentation
    path('api/schema/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
