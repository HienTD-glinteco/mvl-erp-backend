import sentry_sdk
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_standardized_errors.handler import exception_handler as drf_exception_handler
from rest_framework.exceptions import ValidationError as DRFValidationError


def exception_handler(exc, context):
    # Convert Django ValidationError to DRF ValidationError for proper handling
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "error_dict"):
            exc = DRFValidationError(detail=exc.message_dict)
        elif hasattr(exc, "error_list"):
            exc = DRFValidationError(detail=exc.messages)
        else:
            exc = DRFValidationError(
                detail={"non_field_errors": exc.messages if hasattr(exc, "messages") else [str(exc)]}
            )

    # call drf_standardized_errors
    response = drf_exception_handler(exc, context)

    # If response is None --> raise the exception to let Sentry capture it
    if response is None:
        sentry_sdk.capture_exception(exc)
        raise exc

    # If status code is 5xx, capture the exception with Sentry
    if response.status_code >= 500:
        sentry_sdk.capture_exception(exc)

    return response
