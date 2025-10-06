import threading
from contextlib import contextmanager

_thread_locals = threading.local()


def get_current_request():
    """Get the current request from thread-local storage."""
    return getattr(_thread_locals, "request", None)


def get_current_user():
    """Get the current user from thread-local storage."""
    request = get_current_request()
    if request and hasattr(request, "user"):
        return request.user
    return None


def set_current_request(request):
    """
    Set the current request in thread-local storage.

    This should be called at the beginning of API request processing
    to make the request context available to audit logging signals.

    Args:
        request: The Django/DRF request object
    """
    _thread_locals.request = request


def clear_current_request():
    """Clear the current request from thread-local storage."""
    if hasattr(_thread_locals, "request"):
        del _thread_locals.request


@contextmanager
def audit_context(request):
    """
    Context manager to set audit logging context for a request.

    Use this in API views/viewsets to enable audit logging for the duration
    of the request processing.

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            def create(self, request, *args, **kwargs):
                with audit_context(request):
                    return super().create(request, *args, **kwargs)

    Args:
        request: The Django/DRF request object

    Yields:
        None
    """
    set_current_request(request)
    try:
        yield
    finally:
        clear_current_request()
