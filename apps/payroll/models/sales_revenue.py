from datetime import date

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin


@audit_logging_register
class SalesRevenue(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Sales revenue model for tracking employee sales performance.

    This model stores monthly sales revenue information for sales employees
    with automatic code generation and payroll status tracking.

    Attributes:
        id: Auto-increment primary key
        code: Auto-generated unique code in format SR-{YYYYMM}-{seq}
        employee: Foreign key to Employee model
        revenue: Sales revenue amount in VND (integer, must be positive)
        transaction_count: Number of transactions (integer, must be non-negative)
        month: Month as first day of the month
        status: Payroll calculation status (NOT_CALCULATED or CALCULATED)
        created_at/updated_at: Audit timestamps
        created_by/updated_by: Audit user references
    """

    CODE_PREFIX = "SR"

    class SalesRevenueStatus(models.TextChoices):
        NOT_CALCULATED = "NOT_CALCULATED", "Not calculated"
        CALCULATED = "CALCULATED", "Calculated"

    VARIANT_MAPPING = {
        "status": {
            SalesRevenueStatus.NOT_CALCULATED: ColorVariant.GREY,
            SalesRevenueStatus.CALCULATED: ColorVariant.RED,
        }
    }

    code = models.CharField(max_length=50, unique=True, editable=False, db_index=True, verbose_name="Code")
    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="sales_revenues",
        verbose_name="Employee",
    )
    kpi_target = models.BigIntegerField(
        validators=[MinValueValidator(0)], verbose_name="KPI Target", default=50_000_000
    )
    revenue = models.BigIntegerField(validators=[MinValueValidator(0)], verbose_name="Revenue")
    transaction_count = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="Transaction count")
    month = models.DateField(db_index=True, help_text="First day of the revenue month", verbose_name="Month")
    status = models.CharField(
        max_length=20,
        choices=SalesRevenueStatus.choices,
        default=SalesRevenueStatus.NOT_CALCULATED,
        db_index=True,
        editable=False,
        verbose_name="Status",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_revenues_created",
        verbose_name="Created by",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_revenues_updated",
        verbose_name="Updated by",
    )

    class Meta:
        verbose_name = "Sales Revenue"
        verbose_name_plural = "Sales Revenues"
        db_table = "payroll_sales_revenue"
        ordering = ["-created_at"]
        unique_together = [["employee", "month"]]
        indexes = [
            models.Index(fields=["month"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["employee", "month"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.employee.code}"

    @property
    def colored_status(self):
        return self.get_colored_value("status")

    def save(self, *args, **kwargs):
        """Override save to normalize month."""
        # Ensure month is first day of month
        if self.month:
            self.month = date(self.month.year, self.month.month, 1)

        super().save(*args, **kwargs)

    def reset_status_to_not_calculated(self):
        """Reset status to NOT_CALCULATED (used when editing)."""
        self.status = self.SalesRevenueStatus.NOT_CALCULATED
        self.save(update_fields=["status"])
