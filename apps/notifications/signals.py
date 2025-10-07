from django.dispatch import Signal, receiver

from .models import Notification
from .tasks import send_notification_email_task, send_push_notification_task

notification_signal = Signal()


def trigger_send_notification(notification: Notification) -> None:
    """Trigger custom event for sending notification."""
    notification_signal.send(sender=Notification, notification=notification)


def trigger_send_notifications(notifications: list[Notification], delivery_method: str) -> None:
    """Trigger custom event for sending notification."""
    notification_signal.send(sender=Notification, notifications=notifications, delivery_method=delivery_method)


@receiver(notification_signal)
def handle_send_notification(sender, **kwargs):
    """Handle the sending of notification. Bare function implementation; extend as needed."""
    notification: Notification | None = kwargs.get("notification")
    notifications: list[Notification] | None = kwargs.get("notifications")
    delivery_method: str | None = kwargs.get("delivery_method")

    # Validate input
    if notification is None and notifications is None:
        raise ValueError("Either 'notification' or 'notifications' must be provided.")
    if notifications is not None and delivery_method is None:
        raise ValueError("'delivery_method' must be provided when sending multiple notifications.")

    # Send notification(s)
    notification_ids = None
    method = None
    if notification is not None:
        method = notification.delivery_method
        notification_ids = [notification.id]
    elif notifications is not None:
        method = delivery_method
        notification_ids = [notif.id for notif in notifications]

    if not notification_ids:
        return

    if method in [Notification.DeliveryMethod.EMAIL, Notification.DeliveryMethod.BOTH]:
        [send_notification_email_task.delay(notification_id) for notification_id in notification_ids]
    if method in [Notification.DeliveryMethod.FIREBASE, Notification.DeliveryMethod.BOTH]:
        [send_push_notification_task.delay(notification_id) for notification_id in notification_ids]
