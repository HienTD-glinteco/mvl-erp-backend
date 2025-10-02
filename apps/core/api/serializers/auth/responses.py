"""Response serializers for API documentation.

These serializers are used ONLY for drf-spectacular to generate accurate
API documentation. They are not used for actual serialization/validation.
"""

from rest_framework import serializers


class TokensSerializer(serializers.Serializer):
    """JWT tokens response."""

    access = serializers.CharField(help_text="JWT access token")
    refresh = serializers.CharField(help_text="JWT refresh token")


class UserBasicInfoSerializer(serializers.Serializer):
    """Basic user information."""

    id = serializers.UUIDField(help_text="User ID")
    username = serializers.CharField(help_text="Username")
    email = serializers.EmailField(help_text="Email address")
    full_name = serializers.CharField(help_text="Full name")


class LoginResponseSerializer(serializers.Serializer):
    """Login endpoint response."""

    message = serializers.CharField(help_text="Thông báo kết quả")
    username = serializers.CharField(help_text="Tên đăng nhập")
    email_hint = serializers.CharField(help_text="Email đã được che (ví dụ: tes***@example.com)")


class OTPVerificationResponseSerializer(serializers.Serializer):
    """OTP verification response."""

    message = serializers.CharField(help_text="Thông báo kết quả")
    user = UserBasicInfoSerializer(help_text="Thông tin người dùng")
    tokens = TokensSerializer(help_text="JWT tokens")


class PasswordResetResponseSerializer(serializers.Serializer):
    """Password reset request response."""

    message = serializers.CharField(help_text="Thông báo kết quả")
    reset_token = serializers.CharField(help_text="Reset token UUID để sử dụng trong các bước tiếp theo")
    email_hint = serializers.CharField(required=False, allow_null=True, help_text="Email đã được che (nếu dùng email)")
    phone_hint = serializers.CharField(
        required=False, allow_null=True, help_text="Số điện thoại đã được che (nếu dùng SMS)"
    )
    expires_at = serializers.DateTimeField(help_text="Thời gian hết hạn của reset token")


class PasswordResetOTPVerificationResponseSerializer(serializers.Serializer):
    """Password reset OTP verification response."""

    message = serializers.CharField(help_text="Thông báo kết quả")
    tokens = TokensSerializer(help_text="JWT tokens để sử dụng cho bước đổi mật khẩu")


class PasswordResetChangePasswordResponseSerializer(serializers.Serializer):
    """Password reset change password response."""

    message = serializers.CharField(help_text="Thông báo kết quả")


class PasswordChangeResponseSerializer(serializers.Serializer):
    """Password change response."""

    message = serializers.CharField(help_text="Thông báo kết quả")


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Token refresh response."""

    access = serializers.CharField(help_text="JWT access token mới")
    refresh = serializers.CharField(help_text="JWT refresh token mới (nếu rotation được bật)")
