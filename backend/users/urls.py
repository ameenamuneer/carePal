from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.permissions import AllowAny
from .views import (
    UserRegistrationView,
    LoginView,
    LogoutView,
    UserProfileView,
    ClinicalRelationshipViewSet,
)


class PublicTokenRefreshView(TokenRefreshView):
    """Token refresh must not reject requests that carry an expired access token."""
    authentication_classes = []
    permission_classes = [AllowAny]


app_name = 'users'

router = DefaultRouter()
router.register(r'clinical-relationships', ClinicalRelationshipViewSet, basename='clinical-relationship')

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', PublicTokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('', include(router.urls)),
]
