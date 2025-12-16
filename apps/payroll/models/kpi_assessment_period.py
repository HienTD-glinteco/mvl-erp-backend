from django.conf import settings
from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class KPIAssessmentPeriod(BaseModel):
    """KPI Assessment Period model.

    This model represents a KPI assessment period/cycle.
    Each period contains multiple employee and department assessments.

    Attributes:
        month: First day of the assessment month
        kpi_config_snapshot: JSON snapshot of KPIConfig used for this period
        finalized: Whether the entire period is locked (no further edits)
        created_by: User who created this period
        updated_by: User who last updated this period
        note: Additional notes or comments
    """

    month = models.DateField(
        unique=True,
        verbose_name="Assessment month",
        help_text="First day of the assessment month",
    )

    kpi_config_snapshot = models.JSONField(
        verbose_name="KPI config snapshot",
        help_text="Snapshot of KPIConfig used for this assessment period",
    )

    finalized = models.BooleanField(
        default=False,
        verbose_name="Finalized",
        help_text="Whether the entire assessment period is locked (no further edits)",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kpi_periods_created",
        verbose_name="Created by",
        help_text="User who created this period",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kpi_periods_updated",
        verbose_name="Updated by",
        help_text="User who last updated this period",
    )

    note = models.TextField(
        blank=True,
        verbose_name="Note",
        help_text="Additional notes or comments",
    )

    class Meta:
        verbose_name = "KPI Assessment Period"
        verbose_name_plural = "KPI Assessment Periods"
        db_table = "payroll_kpi_assessment_period"
        ordering = ["-month"]
        indexes = [
            models.Index(fields=["month"]),
            models.Index(fields=["finalized"]),
        ]

    def __str__(self):
        return f"KPI Period {self.month.strftime('%Y-%m')} - {'Finalized' if self.finalized else 'Open'}"
