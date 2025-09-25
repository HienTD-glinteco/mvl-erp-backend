import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
import sentry_sdk

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self, user_id, user_email, user_full_name, employee_code, otp_code):
    """Send OTP email via Celery task"""
    try:
        context = {
            'user': {
                'get_full_name': lambda: user_full_name,
                'employee_code': employee_code,
            },
            'otp_code': otp_code,
            'current_year': timezone.now().year,
        }
        
        try:
            html_message = render_to_string('emails/otp_email.html', context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render OTP email template for user {employee_code}: {str(e)}")
            raise
        
        plain_message = f"""
Xin chào {user_full_name or employee_code},

Mã OTP để hoàn tất đăng nhập của bạn là: {otp_code}

Mã này có hiệu lực trong 5 phút.

Nếu bạn không thực hiện đăng nhập này, vui lòng bỏ qua email này.

Trân trọng,
Đội ngũ MaiVietLand
        """
        
        send_mail(
            subject="Mã OTP đăng nhập - MaiVietLand",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        
        logger.info(f"OTP email sent successfully to user {employee_code}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send OTP email to user {employee_code}: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email_task(self, user_id, user_email, user_full_name, employee_code, phone_number=None):
    """Send password reset email via Celery task"""
    try:
        context = {
            'user': {
                'get_full_name': lambda: user_full_name,
                'employee_code': employee_code,
                'email': user_email,
                'phone_number': phone_number,
            },
            'current_year': timezone.now().year,
        }
        
        try:
            html_message = render_to_string('emails/password_reset_email.html', context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render password reset email template for user {employee_code}: {str(e)}")
            raise
        
        plain_message = f"""
Xin chào {user_full_name or employee_code},

Chúng tôi đã nhận được yêu cầu đặt lại mật khẩu cho tài khoản {employee_code}.

Để đảm bảo an toàn, vui lòng liên hệ trực tiếp với quản trị viên hệ thống để được hỗ trợ đặt lại mật khẩu.

Liên hệ hỗ trợ:
- Email: support@maivietland.com
- Điện thoại: (028) 1234 5678
- Thời gian làm việc: 8:00 - 17:00 (Thứ 2 - Thứ 6)

Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email này.

Trân trọng,
Đội ngũ MaiVietLand
        """
        
        send_mail(
            subject="Yêu cầu đặt lại mật khẩu - MaiVietLand",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        
        logger.info(f"Password reset email sent successfully to user {employee_code}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset email to user {employee_code}: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)