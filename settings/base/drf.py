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
        "apps.core.api.permissions.RoleBasedPermission",
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
    "DEFAULT_PAGINATION_CLASS": "libs.drf.pagination.PageNumberWithSizePagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "libs.drf.spectacular.field_filtering.EnhancedAutoSchema",
    "EXCEPTION_HANDLER": "libs.drf.custom_exception_handler.exception_handler",
    # "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
}

# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    "TITLE": "MaiVietLand Backend API",
    "DESCRIPTION": "API documentation for MaiVietLand backend system",
    "VERSION": config("API_DOC_VERSION", default="1.0.0"),
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATION_PARAMETERS": lambda parameter: parameter["name"],
    "TAGS": [],
    "SCHEMA_PATH_PREFIX": "/api/",
    "POSTPROCESSING_HOOKS": [
        "libs.drf.spectacular.schema_hooks.wrap_with_envelope",
        "settings.schema_sorting.sort_schema_by_tags",
    ],
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
