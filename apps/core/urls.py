from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)

from .api.views import LoginView, OTPVerificationView, PasswordResetView

app_name = "core"

urlpatterns = [
    # Authentication endpoints
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/verify-otp/", OTPVerificationView.as_view(), name="verify_otp"),
    path("auth/forgot-password/", PasswordResetView.as_view(), name="forgot_password"),
    
    # JWT token endpoints
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
]
