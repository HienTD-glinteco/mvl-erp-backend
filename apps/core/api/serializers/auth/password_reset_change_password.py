import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.models import PasswordResetOTP
from apps.core.utils.jwt import revoke_user_outstanding_tokens

logger = logging.getLogger(__name__)


class PasswordResetChangePasswordSerializer(serializers.Serializer):
    """
    Step 3: Authenticated request to change password after OTP verification.
    Accepts only new_password and confirm_password.
    Requires that the authenticated user has a verified, unused reset request.
    """

    new_password = serializers.CharField(
        write_only=True,
        help_text="Mật khẩu mới",
        error_messages={
            "required": "Vui lòng nhập mật khẩu mới.",
            "blank": "Mật khẩu mới không được để trống.",
        },
    )
    confirm_password = serializers.CharField(
        write_only=True,
        help_text="Xác nhận mật khẩu mới",
        error_messages={
            "required": "Vui lòng xác nhận mật khẩu mới.",
            "blank": "Xác nhận mật khẩu không được để trống.",
        },
    )

    def validate_new_password(self, value):
        """Validate new password against Django's password validators"""
        if not value:
            raise serializers.ValidationError("Mật khẩu mới không được để trống.")

        # Use Django's password validation
        try:
            validate_password(value)
        except DjangoValidationError as e:
            msgs = e.messages if hasattr(e, "messages") else [str(e)]
            raise serializers.ValidationError(msgs)

        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            raise serializers.ValidationError("Yêu cầu xác thực không hợp lệ.")

        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")
        # Check if passwords match
        if new_password != confirm_password:
            raise serializers.ValidationError("Mật khẩu mới và xác nhận mật khẩu không khớp.")

        # Ensure there is a verified, unused reset request for this user
        reset_request = (
            PasswordResetOTP.objects.filter(
                user=request.user,
                is_verified=True,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )
        if not reset_request:
            raise serializers.ValidationError("Không tìm thấy yêu cầu đặt lại mật khẩu đã xác thực.")

        # Check if user is active
        if not reset_request.user.is_active:
            raise serializers.ValidationError("Tài khoản đã bị vô hiệu hóa.")

        # Check expiration
        if reset_request.is_expired():
            raise serializers.ValidationError("Yêu cầu đặt lại mật khẩu đã hết hạn.")

        attrs["reset_request"] = reset_request
        attrs["user"] = request.user
        return attrs

    def save(self):
        """Change user password and delete OTP record"""
        reset_request = self.validated_data["reset_request"]
        user = self.validated_data["user"]
        new_password = self.validated_data["new_password"]

        # Change password
        user.set_password(new_password)
        user.save()

        # Cleanup reset request
        reset_request.delete_after_use()

        # Invalidate sessions and revoke tokens
        user.invalidate_all_sessions()
        revoke_user_outstanding_tokens(user)

        return user
