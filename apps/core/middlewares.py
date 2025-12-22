import json

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework.response import Response


class ApiResponseWrapperMiddleware(MiddlewareMixin):
    """
    Middleware to wrap API responses in a consistent format.
    """

    def process_response(self, request, response):
        if request.path in ("/docs/", "/schema/", "/docs/mobile/", "/schema/mobile/"):
            return response

        # Only wrap DRF responses or JSON responses
        if isinstance(response, Response):
            status = response.status_code
            data = response.data if response.data else None
        elif isinstance(response, JsonResponse):
            status = response.status_code
            data = json.loads(response.content)
        else:
            # Do not wrap non-JSON responses
            return response

        is_error = getattr(response, "exception", False) or status >= 400
        envelope = {
            "success": not is_error,
            "data": None if is_error else data,
            "error": data if is_error else None,
        }
        # Return a new JsonResponse with the wrapped data
        return JsonResponse(envelope, status=status)
