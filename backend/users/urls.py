from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserRegistrationView,
    LoginView,
    LogoutView,
    UserProfileView,
)

app_name = 'users'

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', UserProfileView.as_view(), name='profile'),
]
