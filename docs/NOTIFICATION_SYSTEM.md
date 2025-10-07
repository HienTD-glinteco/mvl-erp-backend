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

## Firebase Cloud Messaging (FCM) Integration

The notification system now includes Firebase Cloud Messaging (FCM) support for sending push notifications to mobile devices. This integration uses the `firebase-admin` Python SDK for robust and secure communication with Firebase.

### Implementation Status

✅ **Completed**:
- FCM service using `firebase-admin` SDK
- Automatic push notifications via Celery tasks
- UserDevice model extended with FCM token support
- Comprehensive test coverage
- Full documentation

### Architecture

The FCM integration follows a clean architecture:

1. **Configuration** (`settings/base/firebase.py`): Firebase credentials and settings
2. **Model Extension** (`apps/core/models/device.py`): UserDevice stores FCM tokens
3. **Service Layer** (`apps/notifications/fcm_service.py`): FCMService handles Firebase communication
4. **Task Queue** (`apps/notifications/tasks.py`): Celery tasks for asynchronous sending
5. **Integration** (`apps/notifications/utils.py`): Automatic push notification triggering

### Setup Instructions

#### 1. Firebase Project Setup

1. Create or use an existing Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Add your iOS/Android app to the project
3. Go to Project Settings > Service Accounts
4. Click "Generate new private key" to download JSON credentials

#### 2. Environment Configuration

Add these variables to your `.env` file:

```bash
# Enable Firebase Cloud Messaging
FCM_ENABLED=true

# Firebase service account credentials (as JSON string)
FCM_CREDENTIALS_JSON='{"type":"service_account","project_id":"your-project-id",...}'
```

**Security Note**: Never commit credentials to source control. Use environment variables or a secrets manager in production.

#### 3. Database Migration

Run the migration to add FCM support to UserDevice:

```bash
python manage.py migrate core 0006_userdevice_fcm_support
```

#### 4. Install Dependencies

The `firebase-admin` package is included in `pyproject.toml`:

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

### Usage

#### Registering Devices

When users install your mobile app, register their FCM token:

```python
from apps.core.models import UserDevice

device, created = UserDevice.objects.update_or_create(
    user=request.user,
    device_id=device_id,  # Unique device identifier
    defaults={
        'fcm_token': fcm_token,  # From Firebase SDK in mobile app
        'platform': 'android',   # or 'ios', 'web'
        'active': True,
    }
)
```

#### Sending Notifications

Push notifications are sent automatically when using notification utilities:

```python
from apps.notifications.utils import create_notification

# Automatically sends push notification if FCM is enabled
notification = create_notification(
    actor=current_user,
    recipient=target_user,
    verb="commented on your post",
    message="Great work!",
    delivery_method="firebase",  # or "both" for email + push
)
```

#### Manual Push Notifications

Send push notifications directly using FCMService:

```python
from apps.notifications.fcm_service import FCMService

# Using a Notification object
FCMService.send_notification(notification)

# Or directly to a token
FCMService.send_to_token(
    token="user-fcm-token-here",
    title="New Message",
    body="You have a new message from John",
    data={"type": "message", "message_id": "123"}
)
```

### Notification Payload Structure

FCM messages include:

**Notification** (displayed to user):
- `title`: Actor's full name or custom title
- `body`: Verb + message or custom body

**Data** (for app-specific handling):
- `notification_id`: Database notification ID
- `actor_id`: User who triggered the event
- `recipient_id`: User receiving the notification
- `verb`: Action performed
- `created_at`: ISO timestamp
- `target_type` & `target_id`: If a target object exists
- Custom fields from `extra_data`

### Error Handling

The FCM integration includes robust error handling:

- **Unregistered tokens**: Logged but don't block notification creation
- **Invalid arguments**: Validated and logged
- **Network errors**: Retried up to 3 times with exponential backoff (60s, 120s, 240s)
- **Missing device/token**: Gracefully skipped with debug logging

### Testing

Comprehensive tests cover all FCM functionality:

```bash
# Run all FCM tests
poetry run pytest apps/notifications/tests/test_fcm_service.py -v
poetry run pytest apps/notifications/tests/test_tasks.py -v

# Test integration with notification utils
poetry run pytest apps/notifications/tests/test_utils.py -v
```

Tests use mocking to avoid requiring real Firebase credentials.

### Monitoring

All FCM operations are logged:

- **Info**: Successful sends
- **Warning**: Unregistered tokens, inactive devices
- **Error**: Failed sends, configuration issues

Monitor logs for FCM-related issues:

```bash
# Filter for FCM logs
tail -f logs/app.log | grep FCM
```

### Future Enhancements

Potential improvements:

- **Device Management API**: REST endpoints for device registration
- **Topic Subscriptions**: Send notifications to groups of users
- **Notification Templates**: Predefined templates for common events
- **Analytics**: Track notification delivery and engagement
- **Rich Notifications**: Images, actions, and custom layouts

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
