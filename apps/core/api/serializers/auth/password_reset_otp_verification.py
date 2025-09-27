import logging
from rest_framework import serializers

from apps.core.models import PasswordResetOTP

logger = logging.getLogger(__name__)


class PasswordResetOTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying OTP during password reset flow.

    Step 2 of the forgot password flow. User provides the reset_token UUID
    and OTP code they received via email/SMS. Returns otp_token for final step.
    """

    reset_token = serializers.CharField(
        max_length=64,
        help_text="Reset token UUID nhận được từ bước 1",
        error_messages={
            "required": "Vui lòng nhập reset token.",
            "blank": "Reset token không được để trống.",
        },
    )
    otp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text="Mã OTP 6 chữ số",
        error_messages={
            "required": "Vui lòng nhập mã OTP.",
            "blank": "Mã OTP không được để trống.",
            "min_length": "Mã OTP phải có 6 chữ số.",
            "max_length": "Mã OTP phải có 6 chữ số.",
        },
    )

    def validate_reset_token(self, value):
        """Validate reset token"""
        if not value or not value.strip():
            raise serializers.ValidationError("Vui lòng nhập reset token.")
        return value.strip()

    def validate_otp_code(self, value):
        """Validate OTP code format"""
        if not value or not value.strip():
            raise serializers.ValidationError("Vui lòng nhập mã OTP.")

        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError("Mã OTP chỉ được chứa chữ số.")

        if len(value) != 6:
            raise serializers.ValidationError("Mã OTP phải có 6 chữ số.")

        return value

    def validate(self, attrs):
        reset_token = attrs.get("reset_token")
        otp_code = attrs.get("otp_code")

        # Find password reset request by token using manager
        reset_request = PasswordResetOTP.objects.get_by_token(reset_token)
        if not reset_request:
            raise serializers.ValidationError(
                "Reset token không hợp lệ hoặc đã hết hạn."
            )

        # Check if user is active
        if not reset_request.user.is_active:
            raise serializers.ValidationError("Tài khoản đã bị vô hiệu hóa.")

        # Verify OTP
        if not reset_request.verify_otp(otp_code):
            if reset_request.is_expired():
                raise serializers.ValidationError("Mã OTP đã hết hạn.")
            elif reset_request.attempts >= reset_request.max_attempts:
                raise serializers.ValidationError(
                    "Đã vượt quá số lần thử tối đa. Vui lòng yêu cầu OTP mới."
                )
            else:
                raise serializers.ValidationError("Mã OTP không đúng.")

        attrs["reset_request"] = reset_request
        return attrs
