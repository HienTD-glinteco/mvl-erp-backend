from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.views import (
    LoginView,
    MePermissionsView,
    MeUpdateAvatarView,
    MeView,
    MobileBootstrapConfigView,
    PasswordChangeView,
    PasswordResetChangePasswordView,
    PasswordResetOTPVerificationView,
    PasswordResetView,
)
from .api.views.token import TokenRefreshView, TokenVerifyView

app_name = "core"

router = DefaultRouter()

urlpatterns = [
    # Authentication endpoints
    path("auth/login/", LoginView.as_view(), name="login"),
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
    # Mobile bootstrap (startup config)
    path("app/bootstrap/", MobileBootstrapConfigView.as_view(), name="app_bootstrap"),
    # User profile endpoints
    path("me/", MeView.as_view(), name="me"),
    path("me/permissions/", MePermissionsView.as_view(), name="me_permissions"),
    path("me/update-avatar/", MeUpdateAvatarView.as_view(), name="me_update_avatar"),
    # Role management
    path("", include(router.urls)),
]
