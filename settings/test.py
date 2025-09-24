"""
This configuration file overrides some necessary configs
to allow running unittests.
"""

from .base import *  # noqa
from .base import config

import warnings


warnings.simplefilter("ignore", category=RuntimeWarning)


ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ["127.0.0.1"]

CELERY_TASK_ALWAYS_EAGER = False

CACHE_URL = config("CACHE_URL", default="redis://127.0.0.1:6379/2")
CACHE_PREFIX = config("CACHE_PREFIX", default="")
CACHE_TIMEOUT = config(
    "CACHE_TIMEOUT",
    default=24 * 60 * 60 * 30,  # timeout after 30 days
    cast=int,
)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": CACHE_URL,
        "KEY_PREFIX": CACHE_PREFIX + "default",
        "TIMEOUT": CACHE_TIMEOUT,
    },
}
