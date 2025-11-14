from django.apps import AppConfig


class RealestateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.realestate"
    verbose_name = "Real Estate"

    def ready(self):
        """Import signal handlers when app is ready"""
        import apps.realestate.signals  # noqa: F401
