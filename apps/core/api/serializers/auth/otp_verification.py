import logging
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import User

logger = logging.getLogger(__name__)


class OTPVerificationSerializer(serializers.Serializer):
    employee_code = serializers.CharField(
        max_length=100, 
        help_text="Mã nhân viên",
        error_messages={
            'required': 'Vui lòng nhập mã nhân viên.',
            'blank': 'Mã nhân viên không được để trống.'
        }
    )
    otp_code = serializers.CharField(
        max_length=6, 
        min_length=6,
        help_text="Mã OTP",
        error_messages={
            'required': 'Vui lòng nhập mã OTP.',
            'blank': 'Mã OTP không được để trống.',
            'min_length': 'Mã OTP phải có 6 chữ số.',
            'max_length': 'Mã OTP phải có 6 chữ số.'
        }
    )

    def validate_otp_code(self, value):
        """Validate OTP code format"""
        if not value or not value.strip():
            raise serializers.ValidationError("Mã OTP không được để trống.")
        if not value.isdigit():
            raise serializers.ValidationError("Mã OTP chỉ được chứa số.")
        return value.strip()

    def validate(self, attrs):
        employee_code = attrs.get("employee_code")
        otp_code = attrs.get("otp_code")

        try:
            user = User.objects.get(employee_code=employee_code)
        except User.DoesNotExist:
            raise serializers.ValidationError("Mã nhân viên không tồn tại.")

        if not user.verify_otp(otp_code):
            logger.warning(f"Invalid OTP attempt for user {employee_code}")
            raise serializers.ValidationError("Mã OTP không đúng hoặc đã hết hạn.")

        attrs["user"] = user
        return attrs

    def get_tokens(self, user):
        """Generate JWT tokens for user"""
        refresh = RefreshToken.for_user(user)
        
        # Clear OTP after successful login
        user.clear_otp()
        
        logger.info(f"User {user.employee_code} logged in successfully")
        
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
