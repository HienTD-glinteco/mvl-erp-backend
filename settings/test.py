"""
This configuration file overrides some necessary configs
to allow running unittests.
"""

from .base import *  # noqa
from .base.drf import REST_FRAMEWORK

import warnings


warnings.simplefilter("ignore", category=RuntimeWarning)


ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ["127.0.0.1"]

CELERY_TASK_ALWAYS_EAGER = False

# Use in-memory SQLite database for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use local memory cache for tests to avoid Redis dependency
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    },
}

# Disable throttling in tests by setting very high rates
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}

LANGUAGE_CODE = "en"

# Performance optimizations for tests
DEBUG = False
TEMPLATE_DEBUG = False

# Use fast password hasher in tests
# WARNING: MD5PasswordHasher is ONLY for testing! Never use in production.
# This is safe because:
# 1. Test settings are only loaded when ENVIRONMENT=test
# 2. Test data is never used in production
# 3. Test database is separate and ephemeral
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable migrations for faster test DB creation
# Note: Only use this if tests don't depend on custom migrations
# MIGRATION_MODULES = {app: None for app in INSTALLED_APPS}

# Disable logging in tests to improve performance
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
    },
}

# Disable email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
THUMBNAIL_DEFAULT_STORAGE = "django.core.files.storage.FileSystemStorage"
