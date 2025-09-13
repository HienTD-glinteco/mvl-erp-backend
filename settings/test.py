"""
This configuration file overrides some necessary configs
to allow running unittests.
"""

from .base import *  # noqa
import warnings


warnings.simplefilter("ignore", category=RuntimeWarning)


PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
RUNNING_MIGRATE_FLAG = True
TEMPLATE_DEBUG = DEBUG = False

ATOMIC_REQUESTS = False

LOGGING_CONFIG = None
LOG_LEVEL = "ERROR"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_table",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CELERY_TASK_ALWAYS_EAGER = True
