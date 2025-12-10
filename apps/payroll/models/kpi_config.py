from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class KPIConfig(BaseModel):
    """KPI configuration model for storing KPI assessment rules and parameters.

    This model stores the complete KPI configuration including:
    - Grade thresholds mapping percent ranges to grades (A/B/C/D)
    - Unit control rules for grade distribution by unit type
    - Ambiguous assignment policy for overlapping grade ranges

    Only one active configuration should exist at any time.
    When KPI reports are generated, a snapshot of this config is saved with the report.

    Attributes:
        config: JSON field containing all KPI configuration rules
        version: Auto-incrementing version number for tracking changes
    """

    config = models.JSONField(verbose_name="KPI Configuration")
    version = models.PositiveIntegerField(default=1, verbose_name="Version")

    class Meta:
        verbose_name = "KPI Configuration"
        verbose_name_plural = "KPI Configurations"
        db_table = "payroll_kpi_config"
        ordering = ["-version"]

    def __str__(self):
        return f"KPIConfig v{self.version}"

    def save(self, *args, **kwargs):
        """Override save to auto-increment version if not specified."""
        if not self.pk:
            # Get the latest version
            latest = KPIConfig.objects.order_by("-version").first()
            if latest:
                self.version = latest.version + 1
        super().save(*args, **kwargs)
