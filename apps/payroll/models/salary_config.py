from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class SalaryConfig(BaseModel):
    """Salary configuration model for storing salary structure rules and parameters.

    This model stores the complete salary configuration including:
    - Insurance contribution rates and ceilings
    - Personal income tax progressive levels
    - KPI salary grades
    - Business progressive salary levels

    Only one active configuration should exist at any time.
    When payroll is calculated, a snapshot of this config is saved with the payroll record.

    Attributes:
        config: JSON field containing all salary configuration rules
        version: Auto-incrementing version number for tracking changes
    """

    config = models.JSONField(verbose_name="Salary Configuration")
    version = models.PositiveIntegerField(default=1, verbose_name="Version")

    class Meta:
        verbose_name = "Salary Configuration"
        verbose_name_plural = "Salary Configurations"
        db_table = "payroll_salary_config"
        ordering = ["-version"]

    def __str__(self):
        return f"SalaryConfig v{self.version}"

    def save(self, *args, **kwargs):
        """Override save to auto-increment version if not specified."""
        if not self.pk:
            # Get the latest version
            latest = SalaryConfig.objects.order_by("-version").first()
            if latest:
                self.version = latest.version + 1
        super().save(*args, **kwargs)
