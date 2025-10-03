import logging

import sentry_sdk
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self, user_id, user_email, user_full_name, username, otp_code):
    """Send OTP email via Celery task"""
    try:
        context = {
            "user": {
                "get_full_name": lambda: user_full_name,
                "username": username,
            },
            "otp_code": otp_code,
            "current_year": timezone.now().year,
        }

        try:
            html_message = render_to_string("emails/otp_email.html", context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render OTP email template for user {username}: {str(e)}")
            raise

        plain_message = _("""
Hello %(name)s,

Your OTP code to complete login is: %(otp_code)s

This code is valid for 5 minutes.

If you did not initiate this login, please ignore this email.

Best regards,
MaiVietLand Team
        """) % {"name": user_full_name or username, "otp_code": otp_code}

        send_mail(
            subject=_("Login OTP Code - MaiVietLand"),
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )

        logger.info(f"OTP email sent successfully to user {username}")
        return True

    except Exception as e:
        logger.error(f"Failed to send OTP email to user {username}: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email_task(self, user_id, user_email, user_full_name, username, phone_number=None):
    """Send password reset email via Celery task"""
    try:
        context = {
            "user": {
                "get_full_name": lambda: user_full_name,
                "username": username,
                "email": user_email,
                "phone_number": phone_number,
            },
            "current_year": timezone.now().year,
        }

        try:
            html_message = render_to_string("emails/password_reset_email.html", context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render password reset email template for user {username}: {str(e)}")
            raise

        plain_message = _("""
Hello %(name)s,

We have received a password reset request for account %(username)s.

For security reasons, please contact the system administrator directly for password reset assistance.

Support contact:
- Email: support@maivietland.com
- Phone: (028) 1234 5678
- Working hours: 8:00 - 17:00 (Monday - Friday)

If you did not make this request, please ignore this email.

Best regards,
MaiVietLand Team
        """) % {"name": user_full_name or username, "username": username}

        send_mail(
            subject=_("Password Reset Request - MaiVietLand"),
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )

        logger.info(f"Password reset email sent successfully to user {username}")
        return True

    except Exception as e:
        logger.error(f"Failed to send password reset email to user {username}: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)
