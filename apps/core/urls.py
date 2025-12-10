from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.imports.api.views import ImportStatusView

from .api.views import (
    AdministrativeUnitViewSet,
    ConstantsView,
    DeviceChangeRequestView,
    DeviceChangeVerifyOTPView,
    ExportStatusView,
    LoginView,
    MePermissionsView,
    MeUpdateAvatarView,
    MeView,
    NationalityViewSet,
    OTPVerificationView,
    PasswordChangeView,
    PasswordResetChangePasswordView,
    PasswordResetOTPVerificationView,
    PasswordResetView,
    PermissionViewSet,
    ProvinceViewSet,
    RoleViewSet,
)
from .api.views.token import TokenRefreshView, TokenVerifyView

app_name = "core"

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"permissions", PermissionViewSet, basename="permission")
router.register(r"provinces", ProvinceViewSet, basename="province")
router.register(r"administrative-units", AdministrativeUnitViewSet, basename="administrative-unit")
router.register(r"nationalities", NationalityViewSet, basename="nationality")

urlpatterns = [
    # Authentication endpoints
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/verify-otp/", OTPVerificationView.as_view(), name="verify_otp"),
    # Device Change endpoints
    path("auth/device-change/request/", DeviceChangeRequestView.as_view(), name="device_change_request"),
    path("auth/device-change/verify-otp/", DeviceChangeVerifyOTPView.as_view(), name="device_change_verify_otp"),
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
    # User profile endpoints
    path("me/", MeView.as_view(), name="me"),
    path("me/permissions/", MePermissionsView.as_view(), name="me_permissions"),
    path("me/update-avatar/", MeUpdateAvatarView.as_view(), name="me_update_avatar"),
    # Role management
    path("", include(router.urls)),
    # Constants endpoint
    path("constants/", ConstantsView.as_view(), name="constants"),
    # Export status endpoint
    path("export/status/", ExportStatusView.as_view(), name="export_status"),
    # Import status endpoint
    path("import/status/", ImportStatusView.as_view(), name="import_status"),
]
