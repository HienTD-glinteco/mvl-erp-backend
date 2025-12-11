from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class KPICriterion(BaseModel):
    """KPI criterion model for defining evaluation criteria for KPI assessment.

    This model stores individual KPI evaluation criteria that are used when
    generating KPI reports for employees. Each criterion has:
    - Target (e.g., 'sales', 'backoffice')
    - Evaluation type (e.g., 'job performance', 'discipline')
    - Component total score (percentage value 0-100)
    - Active flag for soft-delete functionality

    Attributes:
        target: Target group or role this criterion applies to
        evaluation_type: Type of evaluation this criterion measures
        name: Name of the criterion
        description: Detailed description of the criterion
        component_total_score: Maximum score (percentage) this criterion can contribute
        ordering: Display order for sorting
        active: Whether this criterion is currently active
        created_by: User who created this criterion
        updated_by: User who last updated this criterion
    """

    target = models.CharField(
        max_length=200,
        verbose_name="Target",
        help_text="Target group or role (e.g., 'sales', 'backoffice')",
    )

    evaluation_type = models.CharField(
        max_length=200,
        verbose_name="Evaluation type",
        help_text="Type of evaluation (e.g., 'job performance', 'discipline')",
    )

    name = models.CharField(
        max_length=255,
        verbose_name="Criterion name",
        help_text="Name of the KPI criterion",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Detailed description of the criterion",
    )

    component_total_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
        verbose_name="Component total score",
        help_text="Maximum percentage score (0-100)",
    )

    ordering = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Display order",
        help_text="Order for sorting and display",
    )

    active = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Whether this criterion is active",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kpi_criteria_created",
        verbose_name="Created by",
        help_text="User who created this criterion",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kpi_criteria_updated",
        verbose_name="Updated by",
        help_text="User who last updated this criterion",
    )

    class Meta:
        verbose_name = "KPI Criterion"
        verbose_name_plural = "KPI Criteria"
        db_table = "payroll_kpi_criterion"
        ordering = ["target", "evaluation_type", "ordering", "name"]
        unique_together = [["target", "evaluation_type", "name"]]
        indexes = [
            models.Index(fields=["target", "evaluation_type"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return f"{self.target} - {self.evaluation_type} - {self.name}"
