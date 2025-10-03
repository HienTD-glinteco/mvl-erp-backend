from datetime import timedelta

from .base import config

REST_FRAMEWORK = {
    # "DEFAULT_RENDERER_CLASSES": [
    #     "libs.renderers.EnvelopeJSONRenderer",
    # ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "1000/minute",
        "login": "5/minute",  # Login specific throttling
        "password_change": "3/hour",  # Password change throttling
    },
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
}

# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    "TITLE": "MaiVietLand Backend API",
    "DESCRIPTION": "API documentation for MaiVietLand backend system",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "SCHEMA_PATH_PREFIX": "/api/",
}

SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": ("Bearer",),
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
    # Ensure a single valid refresh token chain by rotating and blacklisting old ones
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
