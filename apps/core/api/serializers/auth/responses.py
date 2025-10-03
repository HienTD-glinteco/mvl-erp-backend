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

    message = serializers.CharField(help_text="Result message")
    username = serializers.CharField(help_text="Username")
    email_hint = serializers.CharField(help_text="Masked email address (e.g., tes***@example.com)")


class OTPVerificationResponseSerializer(serializers.Serializer):
    """OTP verification response."""

    message = serializers.CharField(help_text="Result message")
    user = UserBasicInfoSerializer(help_text="User information")
    tokens = TokensSerializer(help_text="JWT tokens")


class PasswordResetResponseSerializer(serializers.Serializer):
    """Password reset request response."""

    message = serializers.CharField(help_text="Result message")
    reset_token = serializers.CharField(help_text="Reset token UUID to use in subsequent steps")
    email_hint = serializers.CharField(
        required=False, allow_null=True, help_text="Masked email address (if using email)"
    )
    phone_hint = serializers.CharField(required=False, allow_null=True, help_text="Masked phone number (if using SMS)")
    expires_at = serializers.DateTimeField(help_text="Reset token expiration time")


class PasswordResetOTPVerificationResponseSerializer(serializers.Serializer):
    """Password reset OTP verification response."""

    message = serializers.CharField(help_text="Result message")
    tokens = TokensSerializer(help_text="JWT tokens to use for password change step")


class PasswordResetChangePasswordResponseSerializer(serializers.Serializer):
    """Password reset change password response."""

    message = serializers.CharField(help_text="Result message")


class PasswordChangeResponseSerializer(serializers.Serializer):
    """Password change response."""

    message = serializers.CharField(help_text="Result message")


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Token refresh response."""

    access = serializers.CharField(help_text="New JWT access token")
    refresh = serializers.CharField(help_text="New JWT refresh token (if rotation is enabled)")
