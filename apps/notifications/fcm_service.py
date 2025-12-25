"""Firebase Cloud Messaging service for sending push notifications."""

import logging
from dataclasses import dataclass, field
from typing import Optional

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging

from .models import Notification


@dataclass
class FCMResult:
    """Result of an FCM operation with detailed success/failure information."""

    success: bool
    success_count: int = 0
    failure_count: int = 0
    # Maps token/topic to error message for failures
    failed_tokens: dict[str, str] = field(default_factory=dict)
    # List of successfully processed tokens/topics
    successful_tokens: list[str] = field(default_factory=list)
    # Optional message ID for single sends
    message_id: Optional[str] = None
    # Error message for complete failures
    error: Optional[str] = None

    @property
    def all_succeeded(self) -> bool:
        """Check if all operations succeeded."""
        return self.failure_count == 0 and self.success

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.success


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
            logger.info("FCM is disabled, skipping notification")
            return False

        if not initialize_firebase():
            logger.error("Firebase not initialized, cannot send notification")
            return False

        # Build the notification payload
        payload = cls._build_payload(notification, title, body, data)

        # Logic:
        # IF notification.target_client is set:
        #   Send to all active devices for that client (e.g. mobile).
        # ELSE:
        #   Fetch ALL active devices for the recipient and send to all of them.

        devices_qs = notification.recipient.devices.filter(state='active')

        if notification.target_client:
            devices_qs = devices_qs.filter(client=notification.target_client)

        if not devices_qs.exists():
            logger.info(f"No active devices found for user {notification.recipient.username} (client={notification.target_client or 'all'})")
            return False

        # Extract tokens
        tokens = list(devices_qs.exclude(push_token__isnull=True).exclude(push_token__exact='').values_list('push_token', flat=True))

        if not tokens:
            logger.info(f"No valid push tokens found for user {notification.recipient.username}")
            return False

        # Use multicast if multiple tokens, or single send if just one (though multicast handles one fine)
        # Multicast is more efficient and provides detailed results

        # Note: We need to adapt _build_payload to return what send_multicast expects or adapt here.
        # _build_payload returns a dict with 'notification' and 'data' keys suitable for legacy or v1 send.
        # send_multicast expects title, body, data, tokens arguments.

        return cls.send_multicast(
            tokens=tokens,
            title=payload['notification']['title'],
            body=payload['notification']['body'],
            data=payload['data']
        )

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
            logger.info("FCM is disabled, skipping notification")
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

    # =========================================================================
    # Topic-based messaging methods
    # =========================================================================

    @classmethod
    def send_to_topic(
        cls,
        topic: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> FCMResult:
        """Send a push notification to all devices subscribed to a topic.

        This is useful for broadcast messages where all users subscribed
        to a specific topic should receive the notification.

        Args:
            topic: The topic name (e.g., "news", "announcements", "user_123")
            title: Notification title
            body: Notification body
            data: Optional data payload

        Returns:
            FCMResult with success status and message_id if successful
        """
        if not settings.FCM_ENABLED:
            logger.info("FCM is disabled, skipping notification")
            return FCMResult(success=False, error="FCM is disabled")

        if not initialize_firebase():
            logger.error("Firebase not initialized, cannot send notification")
            return FCMResult(success=False, error="Firebase not initialized")

        try:
            # Convert data values to strings (FCM requirement)
            str_data = {k: str(v) for k, v in (data or {}).items()}

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=str_data,
                topic=topic,
            )

            response = messaging.send(message)
            logger.info(f"Successfully sent FCM message to topic '{topic}': {response}")
            return FCMResult(
                success=True,
                success_count=1,
                message_id=response,
                successful_tokens=[topic],
            )

        except ValueError as e:
            logger.error(f"Invalid argument for FCM topic message: {e}")
            return FCMResult(success=False, error=str(e), failed_tokens={topic: str(e)})
        except Exception as e:
            logger.error(f"Failed to send FCM notification to topic '{topic}': {e}")
            return FCMResult(success=False, error=str(e), failed_tokens={topic: str(e)})

    @classmethod
    def _build_topic_result(
        cls,
        tokens: list[str],
        response: "messaging.TopicManagementResponse",
        operation: str,
        topic: str,
    ) -> FCMResult:
        """Build FCMResult from topic subscription/unsubscription response.

        Args:
            tokens: List of FCM tokens that were processed
            response: Firebase TopicManagementResponse
            operation: Operation name for logging ("subscription" or "unsubscription")
            topic: Topic name for logging

        Returns:
            FCMResult with detailed success/failure information
        """
        success_count = response.success_count
        failure_count = response.failure_count

        # Build error index mapping for O(1) lookup
        error_map = {error.index: error.reason for error in response.errors}

        failed_tokens: dict[str, str] = {}
        successful_tokens: list[str] = []

        for idx, token in enumerate(tokens):
            if idx in error_map:
                failed_tokens[token] = error_map[idx]
            else:
                successful_tokens.append(token)

        if failure_count > 0:
            logger.warning(f"Topic {operation} '{topic}': {success_count} succeeded, {failure_count} failed")
            for token, reason in failed_tokens.items():
                logger.debug(f"Token {token[:20]}... failed: {reason}")
        else:
            logger.info(f"Successfully {operation} {success_count} tokens to topic '{topic}'")

        return FCMResult(
            success=failure_count == 0,
            success_count=success_count,
            failure_count=failure_count,
            successful_tokens=successful_tokens,
            failed_tokens=failed_tokens,
        )

    @classmethod
    def send_to_topics(
        cls,
        topics: list[str],
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> FCMResult:
        """Send a push notification to multiple topics.

        Args:
            topics: List of topic names
            title: Notification title
            body: Notification body
            data: Optional data payload

        Returns:
            FCMResult with details of which topics succeeded/failed
        """
        successful_topics: list[str] = []
        failed_topics: dict[str, str] = {}

        for topic in topics:
            result = cls.send_to_topic(topic, title, body, data)
            if result.success:
                successful_topics.append(topic)
            else:
                failed_topics[topic] = result.error or "Unknown error"

        return FCMResult(
            success=len(failed_topics) == 0,
            success_count=len(successful_topics),
            failure_count=len(failed_topics),
            successful_tokens=successful_topics,
            failed_tokens=failed_topics,
        )

    @classmethod
    def subscribe_to_topic(
        cls,
        tokens: list[str],
        topic: str,
    ) -> FCMResult:
        """Subscribe one or more FCM tokens to a topic.

        This allows the backend to add devices to a topic so they can
        receive broadcast messages sent to that topic.

        Args:
            tokens: List of FCM tokens to subscribe
            topic: The topic name to subscribe to

        Returns:
            FCMResult with details of which tokens succeeded/failed
        """
        if not settings.FCM_ENABLED:
            logger.info("FCM is disabled, skipping topic subscription")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, "FCM is disabled"),
                error="FCM is disabled",
            )

        if not initialize_firebase():
            logger.error("Firebase not initialized, cannot subscribe to topic")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, "Firebase not initialized"),
                error="Firebase not initialized",
            )

        if not tokens:
            logger.warning("No tokens provided for topic subscription")
            return FCMResult(success=True, success_count=0, failure_count=0)

        try:
            response = messaging.subscribe_to_topic(tokens, topic)
            return cls._build_topic_result(tokens, response, "subscribed", topic)
        except Exception as e:
            logger.error(f"Failed to subscribe tokens to topic '{topic}': {e}")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, str(e)),
                error=str(e),
            )

    @classmethod
    def subscribe_to_topics(
        cls,
        token: str,
        topics: list[str],
    ) -> FCMResult:
        """Subscribe a single FCM token to multiple topics.

        Args:
            token: FCM token to subscribe
            topics: List of topic names to subscribe to

        Returns:
            FCMResult with details of which topics succeeded/failed
        """
        successful_topics: list[str] = []
        failed_topics: dict[str, str] = {}

        for topic in topics:
            result = cls.subscribe_to_topic([token], topic)
            if result.success:
                successful_topics.append(topic)
            else:
                failed_topics[topic] = result.error or "Unknown error"

        return FCMResult(
            success=len(failed_topics) == 0,
            success_count=len(successful_topics),
            failure_count=len(failed_topics),
            successful_tokens=successful_topics,
            failed_tokens=failed_topics,
        )

    @classmethod
    def unsubscribe_from_topic(
        cls,
        tokens: list[str],
        topic: str,
    ) -> FCMResult:
        """Unsubscribe one or more FCM tokens from a topic.

        Args:
            tokens: List of FCM tokens to unsubscribe
            topic: The topic name to unsubscribe from

        Returns:
            FCMResult with details of which tokens succeeded/failed
        """
        if not settings.FCM_ENABLED:
            logger.info("FCM is disabled, skipping topic unsubscription")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, "FCM is disabled"),
                error="FCM is disabled",
            )

        if not initialize_firebase():
            logger.error("Firebase not initialized, cannot unsubscribe from topic")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, "Firebase not initialized"),
                error="Firebase not initialized",
            )

        if not tokens:
            logger.warning("No tokens provided for topic unsubscription")
            return FCMResult(success=True, success_count=0, failure_count=0)

        try:
            response = messaging.unsubscribe_from_topic(tokens, topic)
            result = cls._build_topic_result(tokens, response, "unsubscription", topic)

            if result.failure_count > 0:
                logger.warning(
                    f"Topic unsubscription from '{topic}': {result.success_count} succeeded, {result.failure_count} failed"
                )
                for token_key, reason in result.failed_tokens.items():
                    logger.debug(f"Token {token_key[:20]}... failed: {reason}")
            else:
                logger.info(f"Successfully unsubscribed {result.success_count} tokens from topic '{topic}'")

            return result

        except Exception as e:
            logger.error(f"Failed to unsubscribe tokens from topic '{topic}': {e}")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, str(e)),
                error=str(e),
            )

    @classmethod
    def unsubscribe_from_topics(
        cls,
        token: str,
        topics: list[str],
    ) -> FCMResult:
        """Unsubscribe a single FCM token from multiple topics.

        Args:
            token: FCM token to unsubscribe
            topics: List of topic names to unsubscribe from

        Returns:
            FCMResult with details of which topics succeeded/failed
        """
        successful_topics: list[str] = []
        failed_topics: dict[str, str] = {}

        for topic in topics:
            result = cls.unsubscribe_from_topic([token], topic)
            if result.success:
                successful_topics.append(topic)
            else:
                failed_topics[topic] = result.error or "Unknown error"

        return FCMResult(
            success=len(failed_topics) == 0,
            success_count=len(successful_topics),
            failure_count=len(failed_topics),
            successful_tokens=successful_topics,
            failed_tokens=failed_topics,
        )

    @classmethod
    def send_multicast(
        cls,
        tokens: list[str],
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> FCMResult:
        """Send a push notification to multiple devices at once.

        This is more efficient than calling send_to_token multiple times
        when you need to send the same message to many devices.

        Args:
            tokens: List of FCM tokens (max 500 per call)
            title: Notification title
            body: Notification body
            data: Optional data payload

        Returns:
            FCMResult with details of which tokens succeeded/failed
        """
        if not settings.FCM_ENABLED:
            logger.info("FCM is disabled, skipping multicast")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, "FCM is disabled"),
                error="FCM is disabled",
            )

        if not initialize_firebase():
            logger.error("Firebase not initialized, cannot send multicast")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, "Firebase not initialized"),
                error="Firebase not initialized",
            )

        if not tokens:
            logger.warning("No tokens provided for multicast")
            return FCMResult(success=True, success_count=0, failure_count=0)

        try:
            # Convert data values to strings (FCM requirement)
            str_data = {k: str(v) for k, v in (data or {}).items()}

            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=str_data,
                tokens=tokens,
            )

            response = messaging.send_each_for_multicast(message)
            success_count = response.success_count
            failure_count = response.failure_count

            # Build detailed failure info
            failed_tokens: dict[str, str] = {}
            successful_tokens: list[str] = []

            for token, send_response in zip(tokens, response.responses, strict=True):
                if send_response.success:
                    successful_tokens.append(token)
                else:
                    failed_tokens[token] = str(send_response.exception)

            if failure_count > 0:
                logger.warning(f"Multicast send: {success_count} succeeded, {failure_count} failed")
                for token, reason in failed_tokens.items():
                    logger.debug(f"Token {token[:20]}... failed: {reason}")
            else:
                logger.info(f"Successfully sent multicast to {success_count} devices")

            return FCMResult(
                success=failure_count == 0,
                success_count=success_count,
                failure_count=failure_count,
                successful_tokens=successful_tokens,
                failed_tokens=failed_tokens,
            )

        except Exception as e:
            logger.error(f"Failed to send multicast notification: {e}")
            return FCMResult(
                success=False,
                failure_count=len(tokens),
                failed_tokens=dict.fromkeys(tokens, str(e)),
                error=str(e),
            )
