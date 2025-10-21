from .batch import batch_audit_context
from .constants import LogAction
from .decorators import audit_logging_register
from .middleware import audit_context, set_current_request
from .producer import log_audit_event
from .registry import AuditLogRegistry


def __getattr__(name):
    """Lazy import of AuditLoggingMixin to avoid circular imports during Django setup."""
    if name == "AuditLoggingMixin":
        from .api.mixins import AuditLoggingMixin

        return AuditLoggingMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AuditLoggingMixin",
    "LogAction",
    "audit_logging_register",
    "log_audit_event",
    "audit_context",
    "set_current_request",
    "batch_audit_context",
    "AuditLogRegistry",
]
