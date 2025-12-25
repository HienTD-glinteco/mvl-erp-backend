from django.apps import AppConfig


class PayrollConfig(AppConfig):
    """Configuration for Payroll application"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payroll"
    verbose_name = "Payroll Management"

    def ready(self):
        import apps.payroll.signals  # noqa: F401
        from libs import register_auto_code_signal

        from .models import PenaltyTicket, generate_penalty_ticket_code

        # Register auto-code generation for PenaltyTicket
        register_auto_code_signal(
            PenaltyTicket,
            temp_code_prefix=PenaltyTicket.TEMP_CODE_PREFIX,
            custom_generate_code=generate_penalty_ticket_code,
        )
