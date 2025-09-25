import logging
from rest_framework import serializers
import sentry_sdk

from apps.core.models import User
from apps.core.tasks import send_password_reset_email_task

logger = logging.getLogger(__name__)


class PasswordResetSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        max_length=255, 
        help_text="Email hoặc số điện thoại",
        error_messages={
            'required': 'Vui lòng nhập email hoặc số điện thoại.',
            'blank': 'Email hoặc số điện thoại không được để trống.'
        }
    )

    def validate_identifier(self, value):
        """Validate identifier (email or phone number)"""
        if not value or not value.strip():
            raise serializers.ValidationError("Vui lòng nhập email hoặc số điện thoại.")
        return value.strip()

    def validate(self, attrs):
        identifier = attrs.get("identifier")

        # Search by email or phone number
        user = None
        try:
            if '@' in identifier:
                # Assume it's an email
                user = User.objects.get(email=identifier)
            else:
                # Assume it's a phone number
                user = User.objects.get(phone_number=identifier)
        except User.DoesNotExist:
            raise serializers.ValidationError("Không tìm thấy tài khoản với thông tin này.")

        if not user.is_active:
            raise serializers.ValidationError("Tài khoản đã bị vô hiệu hóa.")

        attrs["user"] = user
        return attrs

    def send_reset_email(self, user):
        """Send password reset instructions via email using Celery task"""
        try:
            # Send email via Celery task
            send_password_reset_email_task.delay(
                user_id=str(user.id),
                user_email=user.email,
                user_full_name=user.get_full_name(),
                employee_code=user.employee_code,
                phone_number=user.phone_number
            )
            
            logger.info(f"Password reset email task queued for user {user.employee_code}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue password reset email task for user {user.employee_code}: {str(e)}")
            sentry_sdk.capture_exception(e)
            return False
