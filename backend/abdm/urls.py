from django.urls import path
from abdm import views

urlpatterns = [
    path('registration/init/', views.initiate_registration, name='registration-init'),
    path('registration/verify/', views.verify_otp, name='registration-verify'),
    path('registration/create/', views.create_abha, name='registration-create'),
    
    # Login Flow
    path('login/init/', views.initiate_login_view, name='login-init'),
    path('login/verify/', views.verify_login_view, name='login-verify'),
    path('login/login/', views.complete_login_view, name='login-complete'),

    # Consent Management
    path('consents/approve', views.approve_consent_view, name='consent-approve'),
    path('consents/deny', views.deny_consent_view, name='consent-deny'),

    # Care Contexts
    path('care-contexts/providers', views.linked_providers_view, name='linked-providers'),
    path('care-contexts/linked', views.linked_contexts_view, name='linked-contexts'),

    # Discovery & Linking
    path('care-contexts/discover', views.discover_contexts_view, name='discover-contexts'),
    path('care-contexts/link/init', views.initiate_linking_view, name='link-init'),
    path('care-contexts/link/confirm', views.confirm_linking_view, name='link-confirm'),

    # Requests & Webhooks
    path('requests', views.list_requests_view, name='list-requests'),
    path('webhook', views.abdm_webhook_view, name='abdm-webhook'),
]




