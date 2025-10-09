from django.apps import AppConfig


class HrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.hrm"
    verbose_name = "Human Resource Management"

    def ready(self):
        """Import signal handlers when the app is ready."""
        import apps.hrm.signals  # noqa: F401
