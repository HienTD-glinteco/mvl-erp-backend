"""Celery tasks for sending notifications."""

import logging

import sentry_sdk
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from .fcm_service import FCMService
from .models import Notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_notification_email_task(self, notification_id: int):
    """Send notification email via Celery task.

    Args:
        self: Celery task instance
        notification_id: ID of the notification

    Returns:
        bool: True if email sent successfully

    Raises:
        Exception: If email sending fails after retries
    """
    try:
        # Fetch notification from database
        try:
            notification = Notification.objects.select_related("actor", "recipient").get(id=notification_id)
        except Notification.DoesNotExist:
            logger.error(f"Notification {notification_id} does not exist")
            return False

        # Extract data from notification
        recipient_email = notification.recipient.email
        if not recipient_email:
            logger.warning(f"Recipient {notification.recipient.username} has no email address")
            return False

        recipient_name = notification.recipient.get_full_name() or notification.recipient.username
        actor_name = notification.actor.get_full_name() or notification.actor.username
        verb = notification.verb
        message = notification.message
        target_info = str(notification.target) if notification.target else ""

        context = {
            "recipient_name": recipient_name,
            "actor_name": actor_name,
            "verb": verb,
            "message": message,
            "target_info": target_info,
            "current_year": timezone.now().year,
        }

        try:
            html_message = render_to_string("emails/notification_email.html", context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render notification email template for notification {notification_id}: {str(e)}")
            raise

        # Build plain text message
        plain_parts = [
            _("Hello %(recipient_name)s,") % {"recipient_name": recipient_name},
            "",
            _("%(actor_name)s %(verb)s") % {"actor_name": actor_name, "verb": verb},
        ]

        if target_info:
            plain_parts.append(target_info)

        if message:
            plain_parts.extend(["", _("Message:"), message])

        plain_parts.extend(
            [
                "",
                _("Best regards,"),
                _("MaiVietLand Team"),
            ]
        )

        plain_message = "\n".join(plain_parts)

        send_mail(
            subject=_("New Notification - MaiVietLand"),
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )

        logger.info(f"Notification email sent successfully for notification {notification_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send notification email for notification {notification_id}: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)


@shared_task(bind=True, max_retries=3)
def send_push_notification_task(self, notification_id: int):
    """Celery task to send push notification asynchronously.

    Args:
        notification_id: ID of the Notification to send

    The task will retry up to 3 times with exponential backoff
    if an error occurs.
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        success = FCMService.send_notification(notification)

        if success:
            logger.info(f"Push notification sent for notification {notification_id}")
        else:
            logger.warning(f"Push notification failed for notification {notification_id}")

    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} does not exist")
        # Don't retry if notification doesn't exist
        return

    except Exception as exc:
        logger.error(f"Error sending push notification for {notification_id}: {exc}")
        # Retry with exponential backoff: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
