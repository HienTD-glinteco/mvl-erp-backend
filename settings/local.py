"""
This configuration file overrides some necessary configs
to easily develop the app.
"""

from .base import *  # noqa

INSTALLED_APPS += [  # NOQA
    "django.contrib.staticfiles",  # for API admin in local & develop
]

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ["127.0.0.1"]

# CELERY_TASK_ALWAYS_EAGER = True

STATIC_ROOT = "staticfiles"

# Cache settings
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

# Use SMTP:
EMAIL_BACKEND = config(  # noqa
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="127.0.0.1")  # noqa
EMAIL_PORT = config("EMAIL_PORT", default=1025, cast=int)  # noqa
