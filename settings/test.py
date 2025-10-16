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

# Use SQLite for testing to avoid PostgreSQL dependency
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
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/minute",
        "user": "10000/minute",
        "login": "10000/minute",
    },
}

LANGUAGE_CODE = "en"
