from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)

from .api.views import (
    LoginView,
    OTPVerificationView,
    PasswordResetView,
    PasswordResetOTPVerificationView,
    PasswordResetChangePasswordView,
    PasswordChangeView,
)

app_name = "core"

urlpatterns = [
    # Authentication endpoints
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/verify-otp/", OTPVerificationView.as_view(), name="verify_otp"),
    # Password Reset (Forgot Password) Flow - OTP based, no authentication required
    path("auth/forgot-password/", PasswordResetView.as_view(), name="forgot_password"),
    path(
        "auth/forgot-password/verify-otp/",
        PasswordResetOTPVerificationView.as_view(),
        name="forgot_password_verify_otp",
    ),
    path(
        "auth/forgot-password/change-password/",
        PasswordResetChangePasswordView.as_view(),
        name="forgot_password_change_password",
    ),
    # Password Change - requires authentication and current password
    path("auth/change-password/", PasswordChangeView.as_view(), name="change_password"),
    # JWT token endpoints
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
]
