from django.apps import AppConfig


class DevicesConfig(AppConfig):
    """Configuration for the Devices app.

    This app handles device communication and event capture for attendance devices.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.devices"
    verbose_name = "Devices"
