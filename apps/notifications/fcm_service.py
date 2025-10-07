"""Firebase Cloud Messaging service for sending push notifications."""

import logging
from typing import Optional

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging

from .models import Notification

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
_firebase_initialized = False


def initialize_firebase():
    """Initialize Firebase Admin SDK if not already initialized."""
    global _firebase_initialized

    if _firebase_initialized:
        return True

    if not settings.FCM_ENABLED:
        logger.info("FCM is disabled in settings")
        return False

    if not settings.FCM_CREDENTIALS:
        logger.warning("FCM_CREDENTIALS not configured")
        return False

    try:
        cred = credentials.Certificate(settings.FCM_CREDENTIALS)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return False


class FCMService:
    """Service for sending push notifications via Firebase Cloud Messaging."""

    @classmethod
    def send_notification(
        cls,
        notification: Notification,
        title: Optional[str] = None,
        body: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> bool:
        """Send a push notification for a Notification object.

        Args:
            notification: The Notification instance to send
            title: Optional custom title (defaults to actor's full name)
            body: Optional custom body (defaults to verb + message)
            data: Optional custom data payload (defaults to notification metadata)

        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not settings.FCM_ENABLED:
            logger.debug("FCM is disabled, skipping notification")
            return False

        if not initialize_firebase():
            logger.error("Firebase not initialized, cannot send notification")
            return False

        try:
            device = notification.recipient.device
        except Exception:
            logger.debug(f"No device found for user {notification.recipient.username}")
            return False

        if not device or not device.fcm_token or not device.active:
            logger.debug(f"Device not available or inactive for user {notification.recipient.username}")
            return False

        # Build the notification payload
        payload = cls._build_payload(notification, title, body, data)

        # Send via Firebase Admin SDK
        return cls._send_fcm_message(device.fcm_token, payload)

    @classmethod
    def _build_payload(
        cls,
        notification: Notification,
        title: Optional[str] = None,
        body: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> dict:
        """Build FCM notification payload.

        Args:
            notification: The Notification instance
            title: Optional custom title
            body: Optional custom body
            data: Optional custom data

        Returns:
            Dictionary with 'notification' and 'data' keys
        """
        # Default title from actor's full name
        if title is None:
            title = notification.actor.get_full_name() or notification.actor.username

        # Default body from verb and message
        if body is None:
            if notification.message:
                body = f"{notification.verb} {notification.message}"
            else:
                body = notification.verb

        # Default data payload
        if data is None:
            data = {
                "notification_id": str(notification.id),
                "actor_id": str(notification.actor.id),
                "recipient_id": str(notification.recipient.id),
                "verb": notification.verb,
                "created_at": notification.created_at.isoformat(),
            }

            # Add target information if present
            if notification.target and notification.target_content_type is not None:
                data["target_type"] = notification.target_content_type.model
                data["target_id"] = str(notification.target_object_id)

            # Add extra data from notification
            if notification.extra_data:
                data.update(notification.extra_data)

        return {
            "notification": {
                "title": title,
                "body": body,
            },
            "data": data,
        }

    @classmethod
    def _send_fcm_message(cls, fcm_token: str, payload: dict) -> bool:
        """Send a message via Firebase Cloud Messaging.

        Args:
            fcm_token: The FCM token of the target device
            payload: The payload dictionary with 'notification' and 'data' keys

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            # Convert data values to strings (FCM requirement)
            data = {k: str(v) for k, v in payload.get("data", {}).items()}

            # Build the message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=payload["notification"]["title"],
                    body=payload["notification"]["body"],
                ),
                data=data,
                token=fcm_token,
            )

            # Send the message
            response = messaging.send(message)
            logger.info(f"Successfully sent FCM message: {response}")
            return True

        except messaging.UnregisteredError:
            logger.warning(f"FCM token is unregistered: {fcm_token[:10]}...")
            return False
        except ValueError as e:
            logger.error(f"Invalid argument for FCM: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send FCM notification: {e}")
            return False

    @classmethod
    def send_to_token(
        cls,
        token: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> bool:
        """Send a push notification directly to a token.

        Utility method for sending notifications without a Notification object.

        Args:
            token: FCM token
            title: Notification title
            body: Notification body
            data: Optional data payload

        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not settings.FCM_ENABLED:
            logger.debug("FCM is disabled, skipping notification")
            return False

        if not initialize_firebase():
            logger.error("Firebase not initialized, cannot send notification")
            return False

        payload = {
            "notification": {
                "title": title,
                "body": body,
            },
            "data": data or {},
        }

        return cls._send_fcm_message(token, payload)
