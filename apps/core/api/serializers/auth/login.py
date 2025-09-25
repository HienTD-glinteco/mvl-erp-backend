import logging
from django.utils import timezone
from rest_framework import serializers
import sentry_sdk

from apps.core.models import User
from apps.core.tasks import send_otp_email_task

logger = logging.getLogger(__name__)


class LoginSerializer(serializers.Serializer):
    employee_code = serializers.CharField(
        max_length=100, 
        help_text="Mã nhân viên",
        error_messages={
            "required": "Vui lòng nhập mã nhân viên.",
            "blank": "Mã nhân viên không được để trống."
        }
    )
    password = serializers.CharField(
        write_only=True, 
        help_text="Mật khẩu",
        error_messages={
            "required": "Vui lòng nhập mật khẩu.",
            "blank": "Mật khẩu không được để trống."
        }
    )

    def validate_employee_code(self, value):
        """Validate employee code exists"""
        if not value or not value.strip():
            raise serializers.ValidationError("Mã nhân viên không được để trống.")
        return value.strip()

    def validate_password(self, value):
        """Validate password is not empty"""
        if not value:
            raise serializers.ValidationError("Mật khẩu không được để trống.")
        return value

    def validate(self, attrs):
        employee_code = attrs.get("employee_code")
        password = attrs.get("password")

        # Check if user exists
        try:
            user = User.objects.get(employee_code=employee_code)
        except User.DoesNotExist:
            raise serializers.ValidationError("Mã nhân viên không tồn tại.")

        # Check if account is locked
        if user.is_locked:
            remaining_time = (user.locked_until - timezone.now()).seconds // 60
            raise serializers.ValidationError(
                f"Tài khoản đã bị khóa. Vui lòng thử lại sau {remaining_time} phút."
            )

        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError("Tài khoản đã bị vô hiệu hóa.")

        # Verify password
        if not user.check_password(password):
            user.increment_failed_login()
            if user.is_locked:
                logger.warning(f"Account locked for user {employee_code} after failed login attempts")
                raise serializers.ValidationError(
                    "Tài khoản đã bị khóa do đăng nhập sai quá 5 lần. Vui lòng thử lại sau 5 phút."
                )
            logger.warning(f"Failed login attempt for user {employee_code}")
            raise serializers.ValidationError("Mật khẩu không đúng.")

        attrs["user"] = user
        return attrs

    def send_otp_email(self, user):
        """Send OTP via email using Celery task"""
        try:
            otp_code = user.generate_otp()
            
            # Send email via Celery task
            send_otp_email_task.delay(
                user_id=str(user.id),
                user_email=user.email,
                user_full_name=user.get_full_name(),
                employee_code=user.employee_code,
                otp_code=otp_code
            )
            
            logger.info(f"OTP email task queued for user {user.employee_code}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue OTP email task for user {user.employee_code}: {str(e)}")
            sentry_sdk.capture_exception(e)
            return False
