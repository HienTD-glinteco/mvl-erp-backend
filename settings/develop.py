"""
This configuration file overrides some necessary configs
to deploy the app to staging environment.
"""

from decouple import Csv

from .base import *  # noqa
from .base import DEBUG, config

INSTALLED_APPS += [  # NOQA
    "health_check",  # required
    "health_check.db",  # stock Django health checkers
    "health_check.cache",
    "health_check.contrib.s3boto3_storage",
    "health_check.contrib.migrations",
    "health_check.contrib.celery",  # requires celery
    "health_check.contrib.celery_ping",  # requires celery
    "django.contrib.staticfiles",  # for API admin in local & develop
]


ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

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

# Session settings
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"


# CSRF settings
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv())
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", cast=Csv())
CORS_ALLOWED_ORIGIN_REGEXES = config("CORS_ALLOWED_ORIGIN_REGEXES", cast=Csv())

if DEBUG:
    # Use SMTP:
    EMAIL_BACKEND = config(  # noqa
        "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
    )
    EMAIL_HOST = config("EMAIL_HOST", default="127.0.0.1")  # noqa
    EMAIL_PORT = config("EMAIL_PORT", default=1025, cast=int)  # noqa
