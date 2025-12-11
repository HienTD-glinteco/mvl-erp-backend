import sentry_sdk
from drf_standardized_errors.handler import exception_handler as drf_exception_handler


def exception_handler(exc, context):
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
