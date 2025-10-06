"""
Mixins for Django REST Framework ViewSets to enable audit logging.

These mixins automatically set up the audit context for API requests,
ensuring that model changes made during the request are properly logged.
"""

from ..middleware import audit_context


class AuditLoggingMixin:
    """
    Mixin for DRF ViewSets to enable automatic audit logging.

    Add this mixin to any ViewSet where you want model changes to be
    automatically logged with user context.

    Usage:
        class CustomerViewSet(AuditLoggingMixin, viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer

    This mixin overrides the initial() method to set up audit context
    for the entire request lifecycle.
    """

    def initial(self, request, *args, **kwargs):
        """
        Runs anything that needs to occur prior to calling the method handler.

        Wraps the parent initial() call with audit context to enable logging.
        """
        # Set up audit context for this request
        self._audit_context = audit_context(request)
        self._audit_context.__enter__()

        try:
            super().initial(request, *args, **kwargs)
        except Exception:
            # Clean up audit context on error
            self._audit_context.__exit__(None, None, None)
            raise

    def finalize_response(self, request, response, *args, **kwargs):
        """
        Finalizes the response.

        Cleans up the audit context after the response is generated.
        """
        response = super().finalize_response(request, response, *args, **kwargs)

        # Clean up audit context
        if hasattr(self, "_audit_context"):
            self._audit_context.__exit__(None, None, None)

        return response
