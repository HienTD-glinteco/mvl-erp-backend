# Notifications App

This app provides a robust notification system for the MaiVietLand backend application.

## Features

- **User Notifications**: Track events that users should be aware of
- **Flexible Target Objects**: Support for any model via GenericForeignKey
- **Read/Unread Status**: Track which notifications have been read
- **Email Notifications**: Send notifications via email using Celery tasks
- **Multiple Delivery Methods**: Support for Firebase, Email, or both delivery methods
- **RESTful API**: Complete CRUD API with pagination
- **Bulk Operations**: Efficiently mark multiple notifications as read
- **Utility Functions**: Helper functions for creating notifications
- **Admin Interface**: Full admin support for managing notifications

## Models

### Notification

The main model representing a notification with the following fields:

- `actor`: The user who triggered the event (ForeignKey to User)
- `recipient`: The user receiving the notification (ForeignKey to User)
- `verb`: The action that was performed (CharField)
- `target`: Optional object affected by the action (GenericForeignKey)
- `message`: Optional custom message (TextField)
- `read`: Whether the notification has been read (BooleanField)
- `extra_data`: Additional JSON data for context (JSONField)
- `delivery_method`: How to deliver the notification - 'firebase', 'email', or 'both' (CharField)
- `created_at`: When the notification was created (DateTimeField)
- `updated_at`: When the notification was last updated (DateTimeField)

## API Endpoints

All endpoints require authentication and are prefixed with `/api/notifications/`.

### List Notifications
```
GET /api/notifications/
```
Returns a paginated list of notifications for the authenticated user, ordered by newest first.

### Retrieve Notification
```
GET /api/notifications/{id}/
```
Get details of a specific notification.

### Mark as Read
```
PATCH /api/notifications/{id}/mark-as-read/
```
Mark a single notification as read.

### Mark as Unread
```
PATCH /api/notifications/{id}/mark-as-unread/
```
Mark a single notification as unread.

### Bulk Mark as Read
```
POST /api/notifications/bulk-mark-as-read/
```
Mark multiple notifications as read at once.

**Request Body:**
```json
{
  "notification_ids": [1, 2, 3]
}
```

### Mark All as Read
```
POST /api/notifications/mark-all-as-read/
```
Mark all unread notifications for the authenticated user as read.

### Unread Count
```
GET /api/notifications/unread-count/
```
Get the count of unread notifications for the authenticated user.

## Utility Functions

The `apps.notifications.utils` module provides helper functions for creating notifications:

### create_notification

Create a single notification:

```python
from apps.notifications.utils import create_notification

notification = create_notification(
    actor=user1,
    recipient=user2,
    verb="commented on your post",
    target=post_object,  # Optional
    message="This is a great post!",  # Optional
    extra_data={"post_id": 123, "comment_url": "/posts/123#comment-456"},  # Optional
    delivery_method="both"  # Optional: 'firebase', 'email', or 'both' (default: 'firebase')
)
```

### create_bulk_notifications

Create multiple notifications at once:

```python
from apps.notifications.utils import create_bulk_notifications

notifications = create_bulk_notifications(
    actor=user1,
    recipients=[user2, user3, user4],
    verb="mentioned you in a post",
    target=post_object,
    message="Check this out!",
    extra_data={"post_id": 123},  # Optional
    delivery_method="email"  # Optional
)
```

### notify_user

Create a notification, but only if the recipient is not the actor (avoids self-notifications):

```python
from apps.notifications.utils import notify_user

notification = notify_user(
    actor=current_user,
    recipient=post_author,
    verb="commented on your post",
    target=post_object,
    extra_data={"post_id": 123},  # Optional
    delivery_method="both"  # Optional
)
# Returns None if current_user == post_author
```

## Usage Examples

### Creating Notifications

```python
from apps.core.models import User
from apps.notifications.utils import create_notification, notify_user

# Get users
actor = User.objects.get(username="john")
recipient = User.objects.get(username="jane")

# Create a simple notification
notification = create_notification(
    actor=actor,
    recipient=recipient,
    verb="sent you a friend request"
)

# Create a notification with a target object
from apps.hrm.models import Employee
employee = Employee.objects.get(id=123)

notification = create_notification(
    actor=actor,
    recipient=recipient,
    verb="updated employee record for",
    target=employee,
    message="Employee information has been updated"
)

# Avoid self-notifications
def on_comment_created(comment, post):
    """Notify post author when someone comments."""
    notify_user(
        actor=comment.author,
        recipient=post.author,
        verb="commented on your post",
        target=post
    )
    # This won't create a notification if the commenter is the post author
```

### Email Notifications

Notifications can be sent via email by setting the `delivery_method` parameter:

```python
from apps.notifications.utils import create_notification

# Send notification via email only
notification = create_notification(
    actor=actor,
    recipient=recipient,
    verb="assigned you to a task",
    message="Please review the document",
    delivery_method="email"
)

# Send notification via both Firebase and email
notification = create_notification(
    actor=actor,
    recipient=recipient,
    verb="mentioned you in a discussion",
    delivery_method="both"
)

# Default is Firebase only
notification = create_notification(
    actor=actor,
    recipient=recipient,
    verb="liked your post",
    delivery_method="firebase"  # or omit the parameter
)
```

**Note**: Email notifications are sent asynchronously using Celery tasks. The recipient must have a valid email address, otherwise the email will be skipped.

### Querying Notifications

```python
from apps.notifications.models import Notification

# Get all unread notifications for a user
unread = Notification.objects.filter(recipient=user, read=False)

# Get recent notifications
recent = Notification.objects.filter(recipient=user)[:10]

# Mark all as read
Notification.objects.filter(recipient=user, read=False).update(read=True)
```

## Admin Interface

The app includes a Django admin interface for managing notifications. Access it at `/admin/notifications/notification/`.

Features:
- Filter by read status, creation date, and target content type
- Search by actor, recipient, verb, or message
- Bulk actions for marking notifications as read/unread
- Optimized queries with select_related

## Testing

The app includes comprehensive tests covering:
- Model functionality
- API endpoints
- Utility functions
- Email notification tasks
- Notification delivery methods

Run tests with:
```bash
poetry run pytest apps/notifications/tests/ -v
```

## Email Configuration

Email notifications require proper email configuration in your environment settings.

### Development Configuration

In development, emails are printed to the console by default:

```python
# settings/base/email.py
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@maivietland.com"
```

### Production Configuration

For production, configure SMTP settings in your `.env` file:

```bash
# Email settings
DEFAULT_FROM_EMAIL=noreply@maivietland.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

**Supported Email Services:**
- Gmail SMTP (with App Passwords)
- Amazon SES
- SendGrid
- Mailgun
- Any SMTP-compatible service

**Important Notes:**
- Celery must be running for email notifications to be sent asynchronously
- Email templates support both HTML and plain text formats
- All email strings are wrapped with Django's translation functions for i18n support

## Firebase Cloud Messaging (FCM) Integration

The app includes Firebase Cloud Messaging support for sending push notifications to mobile devices.

### Setup

1. **Create a Firebase Project**:
   - Go to [Firebase Console](https://console.firebase.google.com/)
   - Create a new project or use an existing one
   - Add your iOS and/or Android app to the project

2. **Get Service Account Credentials**:
   - In Firebase Console, go to Project Settings > Service Accounts
   - Click "Generate new private key" to download the JSON credentials file

3. **Configure Environment Variables**:
   ```bash
   # Enable FCM
   FCM_ENABLED=true
   
   # Add Firebase credentials as a JSON string
   FCM_CREDENTIALS_JSON='{"type":"service_account","project_id":"your-project",...}'
   ```
   
   **Important**: Never commit the credentials JSON to source control. Use environment variables or a secrets manager.

4. **Update User Device Information**:
   - When users register their devices, store the FCM token:
   ```python
   from apps.core.models import UserDevice
   
   device, created = UserDevice.objects.update_or_create(
       user=user,
       device_id=device_id,
       defaults={
           'fcm_token': fcm_token,
           'platform': 'android',  # or 'ios', 'web'
           'active': True,
       }
   )
   ```

### Usage

Push notifications are sent automatically when you create notifications with `delivery_method="firebase"` or `delivery_method="both"`:

```python
from apps.notifications.utils import create_notification

# This will automatically send a push notification if FCM is enabled
notification = create_notification(
    actor=user1,
    recipient=user2,
    verb="commented on your post",
    message="Great work!",
    delivery_method="firebase",  # or "both" for email + push
)
```

### Manual Push Notification

You can also send push notifications directly using the FCMService:

```python
from apps.notifications.fcm_service import FCMService

# Send notification using a Notification object
FCMService.send_notification(notification)

# Or send directly to a token
FCMService.send_to_token(
    token="user-fcm-token",
    title="New Comment",
    body="John Doe commented on your post",
    data={"post_id": "123", "type": "comment"}
)
```

### Notification Payload

The FCM payload includes:
- **Notification**: Title and body shown to the user
- **Data**: Custom data for app-specific handling
  - `notification_id`: Database ID of the notification
  - `actor_id`: User who triggered the notification
  - `recipient_id`: User receiving the notification
  - `verb`: Action that was performed
  - `created_at`: Timestamp
  - `target_type` and `target_id`: If a target object exists
  - Any extra_data from the notification

### Error Handling

- Invalid or unregistered tokens are logged but don't stop notification creation
- Failed notifications are retried up to 3 times with exponential backoff
- All FCM operations are performed asynchronously via Celery tasks

### Testing FCM

Tests are included for FCM functionality:

```bash
# Run FCM-specific tests
poetry run pytest apps/notifications/tests/test_fcm_service.py -v
poetry run pytest apps/notifications/tests/test_tasks.py -v
```

Mock the Firebase Admin SDK in tests to avoid requiring real credentials.

## Future Enhancements

Potential features for future implementation:

- **WebSocket Integration**: Real-time notification delivery
- **Notification Preferences**: Let users customize which notifications they receive
- **Notification Templates**: Predefined templates for common notification types
- **Notification Grouping**: Group similar notifications together
- **Device Management API**: Endpoints for registering/unregistering devices

## Translation

The app is prepared for internationalization. To update translation files:

```bash
python manage.py makemessages -l vi
# Edit locale/vi/LC_MESSAGES/django.po
python manage.py compilemessages
```

## Architecture Notes

- Uses Django's GenericForeignKey for flexible target object support
- Optimized database queries with indexes on recipient and read status
- Follows the repository's existing patterns for serializers, views, and tests
- Fully compatible with the envelope-based API response format
