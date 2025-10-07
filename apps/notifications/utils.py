"""Utility functions for creating and managing notifications."""

from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import User

from .models import Notification


def create_notification(
    actor: User,
    recipient: User,
    verb: str,
    target: Optional[models.Model] = None,
    message: str = "",
    extra_data: Optional[dict] = None,
    delivery_method: str = "firebase",
) -> Notification:
    """Create a new notification.

    Args:
        actor: The user who triggered the notification
        recipient: The user receiving the notification
        verb: The action that was performed (e.g., "commented on", "liked", "mentioned you in")
        target: Optional target object affected by the action
        message: Optional custom message
        extra_data: Optional dictionary with additional context data
        delivery_method: How to deliver the notification ('firebase', 'email', or 'both')

    Returns:
        The created Notification instance

    Example:
        >>> from apps.core.models import User
        >>> from apps.notifications.utils import create_notification
        >>> actor = User.objects.get(username="john")
        >>> recipient = User.objects.get(username="jane")
        >>> notification = create_notification(
        ...     actor=actor,
        ...     recipient=recipient,
        ...     verb="commented on your post",
        ...     message="Great work!",
        ...     extra_data={"post_id": 123, "comment_url": "/posts/123#comment-456"},
        ...     delivery_method="both"
        ... )
    """
    notification_data = {
        "actor": actor,
        "recipient": recipient,
        "verb": verb,
        "message": message,
        "extra_data": extra_data or {},
        "delivery_method": delivery_method,
    }

    if target:
        notification_data["target_content_type"] = ContentType.objects.get_for_model(target)
        notification_data["target_object_id"] = str(target.pk)

    return Notification.objects.create(**notification_data)


def create_bulk_notifications(
    actor: User,
    recipients: list[User],
    verb: str,
    target: Optional[models.Model] = None,
    message: str = "",
    extra_data: Optional[dict] = None,
    delivery_method: str = "firebase",
) -> list[Notification]:
    """Create multiple notifications for different recipients at once.

    Args:
        actor: The user who triggered the notification
        recipients: List of users receiving the notification
        verb: The action that was performed
        target: Optional target object affected by the action
        message: Optional custom message
        extra_data: Optional dictionary with additional context data
        delivery_method: How to deliver the notification ('firebase', 'email', or 'both')

    Returns:
        List of created Notification instances

    Example:
        >>> from apps.core.models import User
        >>> from apps.notifications.utils import create_bulk_notifications
        >>> actor = User.objects.get(username="john")
        >>> recipients = User.objects.filter(is_active=True)
        >>> notifications = create_bulk_notifications(
        ...     actor=actor,
        ...     recipients=recipients,
        ...     verb="mentioned you in a post",
        ...     message="Check out this update!",
        ...     extra_data={"post_id": 123},
        ...     delivery_method="both"
        ... )
    """
    notification_objects = []
    content_type = None
    target_id = None

    if target:
        content_type = ContentType.objects.get_for_model(target)
        target_id = str(target.pk)

    for recipient in recipients:
        notification_objects.append(
            Notification(
                actor=actor,
                recipient=recipient,
                verb=verb,
                target_content_type=content_type,
                target_object_id=target_id,
                message=message,
                extra_data=extra_data or {},
                delivery_method=delivery_method,
            )
        )

    return Notification.objects.bulk_create(notification_objects)


def notify_user(
    actor: User,
    recipient: User,
    verb: str,
    target: Optional[models.Model] = None,
    message: str = "",
    extra_data: Optional[dict] = None,
    delivery_method: str = "firebase",
) -> Optional[Notification]:
    """Create a notification, but only if the recipient is not the actor.

    This is useful to avoid self-notifications (e.g., when a user comments on their own post).

    Args:
        actor: The user who triggered the notification
        recipient: The user receiving the notification
        verb: The action that was performed
        target: Optional target object affected by the action
        message: Optional custom message
        extra_data: Optional dictionary with additional context data
        delivery_method: How to deliver the notification ('firebase', 'email', or 'both')

    Returns:
        The created Notification instance or None if actor == recipient

    Example:
        >>> from apps.core.models import User
        >>> from apps.notifications.utils import notify_user
        >>> actor = User.objects.get(username="john")
        >>> post_author = User.objects.get(username="jane")
        >>> notification = notify_user(
        ...     actor=actor,
        ...     recipient=post_author,
        ...     verb="commented on your post",
        ...     extra_data={"post_id": 123},
        ...     delivery_method="both"
        ... )
    """
    if actor == recipient:
        return None

    return create_notification(
        actor=actor,
        recipient=recipient,
        verb=verb,
        target=target,
        message=message,
        extra_data=extra_data,
        delivery_method=delivery_method,
    )
