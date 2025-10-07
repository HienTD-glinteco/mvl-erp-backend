"""Firebase Cloud Messaging settings."""

import json

from decouple import config

# Firebase Cloud Messaging
FCM_ENABLED = config("FCM_ENABLED", default=False, cast=bool)

# Firebase credentials (JSON string from service account key file)
FCM_CREDENTIALS_JSON = config("FCM_CREDENTIALS_JSON", default="")

# Parse credentials if provided
FCM_CREDENTIALS = None
if FCM_CREDENTIALS_JSON:
    try:
        FCM_CREDENTIALS = json.loads(FCM_CREDENTIALS_JSON)
    except json.JSONDecodeError:
        FCM_CREDENTIALS = None
