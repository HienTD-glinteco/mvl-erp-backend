from django.apps import AppConfig


class AuditLoggingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit_logging"

    def ready(self):
        """
        Called when Django has loaded all models.

        Resolves string-based AUDIT_LOG_TARGET references to actual model classes.
        """
        from .registry import AuditLogRegistry

        # Resolve all string AUDIT_LOG_TARGET references
        AuditLogRegistry.resolve_targets()
