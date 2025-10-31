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

CELERY_TASK_ALWAYS_EAGER = True

STATIC_ROOT = "staticfiles"

# Use local memory cache for tests to avoid Redis dependency
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    },
}

# Use SMTP:
EMAIL_BACKEND = config(  # noqa
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="127.0.0.1")  # noqa
EMAIL_PORT = config("EMAIL_PORT", default=1025, cast=int)  # noqa
