# Notification System

## Overview

The notification system provides a standardized way to create and manage notifications within the application. It supports in-app notifications with potential for push notification integration.

## Architecture

The notification system follows the repository's established patterns:

```
apps/notifications/
├── models.py              # Notification model
├── api/
│   ├── views/
│   │   └── notification.py   # API views
│   └── serializers/
│       └── notification.py   # Serializers
├── utils.py               # Helper functions
├── admin.py               # Django admin
├── urls.py                # URL routing
└── tests/                 # Test suite
```

## Data Model

### Notification Model

```python
class Notification(BaseModel):
    actor = ForeignKey(User)           # Who triggered the event
    recipient = ForeignKey(User)       # Who receives the notification
    verb = CharField                   # Action performed
    target = GenericForeignKey         # Optional target object
    message = TextField                # Optional custom message
    read = BooleanField                # Read status
    created_at = DateTimeField         # Auto-generated
    updated_at = DateTimeField         # Auto-updated
```

The model uses Django's `GenericForeignKey` to support notifications for any model type.

## API Endpoints

All endpoints are authenticated and prefixed with `/api/notifications/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user's notifications (paginated) |
| GET | `/{id}/` | Retrieve specific notification |
| PATCH | `/{id}/mark-as-read/` | Mark notification as read |
| PATCH | `/{id}/mark-as-unread/` | Mark notification as unread |
| POST | `/bulk-mark-as-read/` | Mark multiple as read |
| POST | `/mark-all-as-read/` | Mark all user's notifications as read |
| GET | `/unread-count/` | Get count of unread notifications |

### API Response Format

All responses follow the repository's envelope pattern:

```json
{
  "success": true,
  "data": {
    "id": 123,
    "actor": {
      "id": "user-uuid",
      "username": "john_doe",
      "full_name": "John Doe"
    },
    "recipient": "user-uuid",
    "verb": "commented on your post",
    "target_type": "blog.post",
    "target_id": "post-id",
    "message": "Great article!",
    "read": false,
    "created_at": "2025-10-03T10:30:00Z",
    "updated_at": "2025-10-03T10:30:00Z"
  },
  "error": null
}
```

## Usage Examples

### Creating Notifications

Use the utility functions from `apps.notifications.utils`:

```python
from apps.notifications.utils import create_notification, notify_user

# Simple notification
notification = create_notification(
    actor=current_user,
    recipient=target_user,
    verb="sent you a friend request"
)

# Notification with target
notification = create_notification(
    actor=current_user,
    recipient=post_author,
    verb="commented on",
    target=post_object,
    message="Great post!"
)

# Avoid self-notifications
notification = notify_user(
    actor=commenter,
    recipient=post_author,  # Won't create if commenter == post_author
    verb="commented on your post",
    target=post
)
```

### Integration in Views

Example of creating notifications when an action occurs:

```python
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.notifications.utils import create_bulk_notifications

@api_view(['POST'])
def create_post(request):
    # Create the post
    post = Post.objects.create(...)

    # Notify followers
    followers = request.user.followers.all()
    create_bulk_notifications(
        actor=request.user,
        recipients=followers,
        verb="created a new post",
        target=post
    )

    return Response({"status": "success"})
```

## Testing

The notification system includes comprehensive tests:

```bash
# Run all notification tests
poetry run pytest apps/notifications/tests/ -v

# Run specific test files
poetry run pytest apps/notifications/tests/test_api.py -v
poetry run pytest apps/notifications/tests/test_models.py -v
poetry run pytest apps/notifications/tests/test_utils.py -v
```

## Future Enhancements

### Firebase Cloud Messaging (FCM) Integration

To add push notification support with Firebase:

#### 1. Setup FCM

Add to `settings/base/base.py`:

```python
# Firebase Cloud Messaging
FCM_SERVER_KEY = config("FCM_SERVER_KEY", default="")
FCM_ENABLED = config("FCM_ENABLED", default=False, cast=bool)
```

#### 2. Extend User Device Model

The `UserDevice` model already exists in `apps.core.models`. Extend it to store FCM tokens:

```python
class UserDevice(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    device_id = models.CharField(max_length=255, unique=True)
    fcm_token = models.CharField(max_length=255, blank=True)  # Add this
    platform = models.CharField(max_length=20)  # 'ios' or 'android'
    active = models.BooleanField(default=True)
```

#### 3. Create FCM Service

Create `apps/notifications/fcm_service.py`:

```python
import logging
from typing import Optional

import requests
from django.conf import settings

from apps.core.models import User
from .models import Notification

logger = logging.getLogger(__name__)


class FCMService:
    """Service for sending push notifications via Firebase Cloud Messaging."""

    FCM_URL = "https://fcm.googleapis.com/fcm/send"

    @classmethod
    def send_notification(cls, notification: Notification) -> bool:
        """Send a push notification for a Notification object."""
        if not settings.FCM_ENABLED:
            return False

        device = notification.recipient.device
        if not device or not device.fcm_token or not device.active:
            return False

        payload = cls._build_payload(notification, device.fcm_token)
        return cls._send_fcm_request(payload)

    @classmethod
    def _build_payload(cls, notification: Notification, fcm_token: str) -> dict:
        """Build FCM payload."""
        return {
            "to": fcm_token,
            "notification": {
                "title": f"{notification.actor.get_full_name()}",
                "body": f"{notification.verb} {notification.message}",
                "sound": "default",
            },
            "data": {
                "notification_id": str(notification.id),
                "actor_id": str(notification.actor.id),
                "verb": notification.verb,
                "created_at": notification.created_at.isoformat(),
            },
        }

    @classmethod
    def _send_fcm_request(cls, payload: dict) -> bool:
        """Send request to FCM."""
        try:
            headers = {
                "Authorization": f"Bearer {settings.FCM_SERVER_KEY}",
                "Content-Type": "application/json",
            }
            response = requests.post(cls.FCM_URL, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"FCM notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send FCM notification: {e}")
            return False
```

#### 4. Create Celery Task

Create `apps/notifications/tasks.py`:

```python
from celery import shared_task
from .fcm_service import FCMService
from .models import Notification


@shared_task(bind=True, max_retries=3)
def send_push_notification(self, notification_id: int):
    """Celery task to send push notification asynchronously."""
    try:
        notification = Notification.objects.get(id=notification_id)
        FCMService.send_notification(notification)
    except Notification.DoesNotExist:
        pass
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

#### 5. Integrate with Utility Functions

Update `apps/notifications/utils.py`:

```python
from .tasks import send_push_notification

def create_notification(...) -> Notification:
    notification = Notification.objects.create(...)

    # Send push notification asynchronously
    if settings.FCM_ENABLED:
        send_push_notification.delay(notification.id)

    return notification
```

#### 6. Add Device Registration Endpoint

Add to `apps/core/api/views/device.py`:

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_device(request):
    """Register user's device for push notifications."""
    device, created = UserDevice.objects.update_or_create(
        user=request.user,
        defaults={
            'device_id': request.data.get('device_id'),
            'fcm_token': request.data.get('fcm_token'),
            'platform': request.data.get('platform'),
            'active': True,
        }
    )
    return Response({
        "message": "Device registered successfully",
        "device_id": device.device_id
    })
```

### WebSocket Integration (Real-time notifications)

For real-time notification delivery, Django Channels can be integrated:

1. Install Django Channels
2. Create a WebSocket consumer for notifications
3. Send notifications via WebSocket when created
4. Update frontend to listen for real-time updates

### Email Notifications

**Status: ✅ IMPLEMENTED**

Email notifications are now fully implemented and supported. The system can send notifications via email asynchronously using Celery tasks.

#### Features

- **Automatic Email Sending**: Notifications with `delivery_method` set to `'email'` or `'both'` automatically trigger email notifications
- **Asynchronous Processing**: Email sending is handled by Celery tasks for better performance
- **HTML and Plain Text**: Email templates support both HTML and plain text formats
- **Translation Support**: All email strings are wrapped with Django's translation functions
- **Retry Logic**: Failed email sends are automatically retried (up to 3 times)

#### Usage

```python
from apps.notifications.utils import create_notification

# Send notification via email
notification = create_notification(
    actor=user1,
    recipient=user2,
    verb="assigned you to a task",
    message="Please review the quarterly report",
    delivery_method="email"
)

# Send via both Firebase and email
notification = create_notification(
    actor=user1,
    recipient=user2,
    verb="mentioned you in a comment",
    delivery_method="both"
)
```

#### Email Template

The email template is located at `apps/notifiations/templates/emails/notification_email.html` and includes:
- Responsive design
- Professional styling
- Support for custom messages
- Target object information
- Internationalization support

#### Configuration

Email settings are configured in `settings/base/email.py`. For production use, set the following environment variables:

```bash
DEFAULT_FROM_EMAIL=noreply@maivietland.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-app-password
```

#### Implementation Details

- **Task**: `apps/notifications/tasks.py::send_notification_email_task`
- **Template**: `apps/notifiations/templates/emails/notification_email.html`
- **Integration**: Automatically triggered in `apps/notifications/utils.py` when creating notifications
- **Tests**: Comprehensive test coverage in `apps/notifications/tests/test_tasks.py`

#### Future Enhancements for Email

- User preferences for email notification types
- Email digest (batch multiple notifications)
- Unsubscribe links
- Rich text formatting for messages
- Attachment support

## Performance Considerations

### Database Indexes

The Notification model includes indexes for optimal query performance:

```python
indexes = [
    models.Index(fields=['recipient', '-created_at']),
    models.Index(fields=['recipient', 'read', '-created_at']),
]
```

### Query Optimization

All API views use `select_related()` to minimize database queries:

```python
queryset = Notification.objects.select_related(
    'actor',
    'target_content_type'
)
```

### Bulk Operations

Use bulk operations when creating multiple notifications:

```python
# Good - Single query
create_bulk_notifications(actor, recipients, verb)

# Bad - Multiple queries
for recipient in recipients:
    create_notification(actor, recipient, verb)
```

## Security Considerations

- ✅ Users can only access their own notifications
- ✅ Bulk operations are scoped to the authenticated user
- ✅ All endpoints require authentication
- ✅ No permission-based notification access (future consideration)

## Monitoring and Maintenance

### Cleanup Old Notifications

Consider adding a periodic task to clean up old read notifications:

```python
# In apps/notifications/tasks.py
from celery import shared_task
from datetime import timedelta
from django.utils import timezone

@shared_task
def cleanup_old_notifications():
    """Delete read notifications older than 90 days."""
    cutoff_date = timezone.now() - timedelta(days=90)
    count = Notification.objects.filter(
        read=True,
        created_at__lt=cutoff_date
    ).delete()
    return f"Deleted {count[0]} old notifications"
```

Add to Celery Beat schedule:

```python
# In settings/base/celery.py
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
    },
}
```

## Troubleshooting

### Notifications Not Appearing

1. Check the user is authenticated
2. Verify the recipient field matches the user
3. Check database indexes are created
4. Ensure middleware is not filtering responses

### Performance Issues

1. Use `select_related()` for related objects
2. Add pagination for large result sets
3. Consider caching unread counts
4. Use database indexes effectively

## References

- Django GenericForeignKey: https://docs.djangoproject.com/en/5.1/ref/contrib/contenttypes/
- Django REST Framework ViewSets: https://www.django-rest-framework.org/api-guide/viewsets/
- Firebase Cloud Messaging: https://firebase.google.com/docs/cloud-messaging
- Celery Tasks: https://docs.celeryproject.org/en/stable/userguide/tasks.html
