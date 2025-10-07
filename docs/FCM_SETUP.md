# Firebase Cloud Messaging (FCM) Setup Guide

This guide provides step-by-step instructions for setting up Firebase Cloud Messaging (FCM) for push notifications.

## Prerequisites

- A Firebase account ([Sign up here](https://firebase.google.com/))
- Admin access to the backend repository
- Access to environment variable configuration (`.env` file or secrets manager)

## Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project" or select an existing project
3. Follow the setup wizard:
   - Enter project name (e.g., "MaiVietLand")
   - Configure Google Analytics (optional)
   - Click "Create project"

## Step 2: Add Your Mobile Apps

### For Android

1. In Firebase Console, click "Add app" and select Android
2. Register app with package name (e.g., `com.maivietland.app`)
3. Download `google-services.json`
4. Follow the integration steps in your Android app

### For iOS

1. In Firebase Console, click "Add app" and select iOS
2. Register app with bundle ID (e.g., `com.maivietland.app`)
3. Download `GoogleService-Info.plist`
4. Follow the integration steps in your iOS app

## Step 3: Generate Service Account Key

1. In Firebase Console, go to **Project Settings** (gear icon)
2. Navigate to **Service Accounts** tab
3. Click **Generate new private key**
4. Confirm and download the JSON file
5. Keep this file secure - it contains sensitive credentials

The downloaded JSON will look like:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/...",
  "universe_domain": "googleapis.com"
}
```

## Step 4: Configure Backend Environment

### Local Development

1. Open or create `.env` file in the project root
2. Add the following configuration:

```bash
# Enable Firebase Cloud Messaging
FCM_ENABLED=true

# Firebase service account credentials (as a single-line JSON string)
FCM_CREDENTIALS_JSON='{"type":"service_account","project_id":"your-project-id",...}'
```

**Important**: Convert the multi-line JSON to a single line by removing newlines within the private key.

### Production/Staging

For production environments, use a secrets manager instead of `.env` files:

#### Using GitHub Secrets (for CI/CD)

1. Go to repository Settings > Secrets and variables > Actions
2. Add secrets:
   - `FCM_ENABLED`: `true`
   - `FCM_CREDENTIALS_JSON`: (paste the entire JSON as a single line)

#### Using AWS Secrets Manager

```bash
aws secretsmanager create-secret \
  --name maivietland/fcm-credentials \
  --secret-string file://firebase-credentials.json
```

Then update application to fetch from AWS Secrets Manager.

#### Using Docker/Kubernetes

```yaml
# docker-compose.yml
environment:
  - FCM_ENABLED=true
  - FCM_CREDENTIALS_JSON=${FCM_CREDENTIALS_JSON}
```

```yaml
# kubernetes secret
apiVersion: v1
kind: Secret
metadata:
  name: firebase-config
type: Opaque
stringData:
  FCM_CREDENTIALS_JSON: |
    {"type":"service_account",...}
```

## Step 5: Verify Configuration

### Check Settings

Verify the settings are loaded correctly:

```bash
python manage.py shell

>>> from django.conf import settings
>>> print(settings.FCM_ENABLED)
True
>>> print(settings.FCM_CREDENTIALS is not None)
True
```

### Test Firebase Connection

Run a quick test to ensure Firebase initializes correctly:

```python
from apps.notifications.fcm_service import initialize_firebase

result = initialize_firebase()
print(f"Firebase initialized: {result}")
```

## Step 6: Register User Devices

### Mobile App Integration

In your mobile app (iOS/Android), integrate the Firebase SDK and obtain the FCM token:

**Android (Kotlin)**:
```kotlin
FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
    if (task.isSuccessful) {
        val token = task.result
        // Send token to backend
        registerDevice(token)
    }
}
```

**iOS (Swift)**:
```swift
Messaging.messaging().token { token, error in
    if let token = token {
        // Send token to backend
        registerDevice(token)
    }
}
```

### Backend Device Registration

Create an API endpoint or use the admin interface to register devices:

```python
from apps.core.models import UserDevice

device, created = UserDevice.objects.update_or_create(
    user=request.user,
    device_id=unique_device_id,
    defaults={
        'fcm_token': fcm_token_from_mobile,
        'platform': 'android',  # or 'ios', 'web'
        'active': True,
    }
)
```

## Step 7: Test Push Notifications

### Send Test Notification

```python
from apps.notifications.utils import create_notification
from apps.core.models import User

actor = User.objects.get(username='admin')
recipient = User.objects.get(username='testuser')

notification = create_notification(
    actor=actor,
    recipient=recipient,
    verb="sent you a test message",
    message="Testing FCM integration",
    delivery_method="firebase"
)
```

### Check Celery Logs

Monitor Celery worker logs to see if the notification was sent:

```bash
# In the terminal running Celery worker
celery -A celery_tasks worker -l info
```

Look for log messages like:
```
[INFO] Successfully sent FCM message: projects/xxx/messages/xxx
[INFO] Push notification sent for notification 123
```

### Verify on Mobile Device

Check if the notification appears on the registered mobile device.

## Troubleshooting

### Issue: "Firebase not initialized"

**Solution**: Check that `FCM_CREDENTIALS_JSON` is properly set and contains valid JSON.

```bash
python manage.py shell
>>> from django.conf import settings
>>> import json
>>> json.loads(settings.FCM_CREDENTIALS_JSON)
```

### Issue: "Unregistered token"

**Solution**: The FCM token may have expired or the app was uninstalled. Request a new token from the mobile app.

### Issue: "Invalid argument"

**Solution**: Check that the FCM token is correctly stored in the UserDevice model and is not empty or corrupted.

### Issue: Notifications not received

**Checklist**:
1. Verify `FCM_ENABLED=true` in environment
2. Check that UserDevice has a valid `fcm_token`
3. Ensure `active=True` on the UserDevice
4. Check Celery is running and processing tasks
5. Review Celery and application logs for errors
6. Verify mobile app has proper Firebase integration
7. Check that notification permissions are granted in mobile app

### Testing Without Mobile App

For testing without a real mobile device, use Firebase Console's "Cloud Messaging" feature to send test messages directly to a token.

## Security Best Practices

1. **Never commit credentials**: Always use environment variables or secrets manager
2. **Rotate keys regularly**: Generate new service account keys periodically
3. **Limit permissions**: Use service accounts with minimal required permissions
4. **Secure storage**: Use encrypted storage for credentials in production
5. **Monitor usage**: Set up Firebase monitoring and alerts for unusual activity
6. **Validate tokens**: Verify FCM tokens before storing in database
7. **Clean up inactive devices**: Regularly remove devices that are no longer active

## Monitoring and Maintenance

### Firebase Console Monitoring

1. Go to Firebase Console > Cloud Messaging
2. Review sending statistics:
   - Messages sent
   - Delivery rate
   - Error rate

### Application Logging

Monitor application logs for FCM-related messages:

```bash
# Production logs
tail -f /var/log/app/backend.log | grep -i fcm

# Docker logs
docker logs -f backend-container | grep -i fcm
```

### Celery Monitoring

Use Flower to monitor Celery tasks:

```bash
celery -A celery_tasks flower
# Visit http://localhost:5555
```

## Additional Resources

- [Firebase Cloud Messaging Documentation](https://firebase.google.com/docs/cloud-messaging)
- [Firebase Admin Python SDK](https://firebase.google.com/docs/admin/setup#python)
- [FCM HTTP v1 API Reference](https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages)
- [Best Practices for FCM](https://firebase.google.com/docs/cloud-messaging/concept-options)

## Support

If you encounter issues not covered in this guide:

1. Check application logs for detailed error messages
2. Review Firebase Console for error reports
3. Consult the [Firebase Support](https://firebase.google.com/support)
4. Contact the backend team for assistance
