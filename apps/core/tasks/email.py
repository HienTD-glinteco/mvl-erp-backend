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

        plain_message = _("""Hello %(name)s,

Your OTP code to complete login is: %(otp_code)s

This code is valid for 5 minutes.

If you did not initiate this login, please ignore this email.

Best regards,
MaiVietLand Team""") % {"name": user_full_name or username, "otp_code": otp_code}

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
def send_otp_device_change_task(self, user_id, user_email, user_full_name, username, otp_code):
    """Send device change OTP email via Celery task"""
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
            html_message = render_to_string("emails/otp_device_change.html", context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render device change OTP email template for user {username}: {str(e)}")
            raise

        plain_message = _("""Hello %(name)s,

We have received a change device request for your MaiVietLand account.

Your OTP code to complete the request is: %(otp_code)s

This code is valid for 5 minutes and can only be used once.

If you did not initiate this login, please ignore this email and contact the administrator if necessary.

Best regards,
MaiVietLand Team""") % {"name": user_full_name or username, "otp_code": otp_code}

        send_mail(
            subject=_("Device Change OTP Code - MaiVietLand"),
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )

        logger.info(f"Device change OTP email sent successfully to user {username}")
        return True

    except Exception as e:
        logger.error(f"Failed to send device change OTP email to user {username}: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email_task(self, user_id, user_email, user_full_name, username, otp_code):
    """Send password reset OTP email via Celery task"""
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
            html_message = render_to_string("emails/password_reset_otp_email.html", context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render password reset OTP email template for user {username}: {str(e)}")
            raise

        plain_message = _("""Hello %(name)s,

We have received a password reset request for your MaiVietLand account.

Your OTP code to reset your password is: %(otp_code)s

This code is valid for 3 minutes and can only be used once.

If you did not initiate this password reset request, please ignore this email.

Best regards,
MaiVietLand Team""") % {"name": user_full_name or username, "otp_code": otp_code}

        send_mail(
            subject=_("Password Reset OTP Code - MaiVietLand"),
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )

        logger.info(f"Password reset OTP email sent successfully to user {username}")
        return True

    except Exception as e:
        logger.error(f"Failed to send password reset OTP email to user {username}: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)
