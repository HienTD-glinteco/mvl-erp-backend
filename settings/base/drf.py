from datetime import timedelta

from .base import config

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": "rest_framework_simplejwt.authentication.JWTAuthentication",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "100/minute", "user": "1000/minute"},
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        seconds=config(
            "ACCESS_TOKEN_LIFETIME",
            default=60 * 60 * 24,  # Default 1 days
            cast=int,
        )
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        seconds=config(
            "REFRESH_TOKEN_LIFETIME",
            default=60 * 60 * 24 * 30,  # Default 30 days
            cast=int,
        )
    ),
}
