from django.apps import AppConfig


class PayrollConfig(AppConfig):
    """Configuration for Payroll application"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payroll"
    verbose_name = "Payroll Management"
