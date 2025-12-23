import uuid
from datetime import date

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs import ColorVariant
from libs.models import BaseModel, ColoredValueMixin


def generate_sales_revenue_code(instance: "SalesRevenue") -> str:
    """Generate sales revenue code in format SR-{YYYYMM}-{seq}.

    Args:
        instance: SalesRevenue instance which MUST have an id and month.

    Returns:
        Generated code string (e.g., "SR-202511-0001")

    Raises:
        ValueError: If the instance has no id or month.
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("SalesRevenue must have an id to generate code")

    if not instance.month:
        raise ValueError("SalesRevenue must have a month to generate code")

    year = instance.month.year
    month = instance.month.month
    month_key = f"{year}{month:02d}"

    max_code = (
        SalesRevenue.objects.filter(month=instance.month, code__startswith=f"SR-{month_key}-")
        .exclude(pk=instance.pk)
        .values_list("code", flat=True)
    )

    max_seq = 0
    for code in max_code:
        try:
            seq_part = code.split("-")[-1]
            seq = int(seq_part)
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    seq = max_seq + 1
    return f"SR-{month_key}-{seq:04d}"


@audit_logging_register
class SalesRevenue(ColoredValueMixin, BaseModel):
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
        """Override save to generate code and normalize month."""
        # Generate temporary code for new instances
        if not self.code:
            self.code = f"TEMP_{uuid.uuid4().hex[:8]}"

        # Ensure month is first day of month
        if self.month:
            self.month = date(self.month.year, self.month.month, 1)

        super().save(*args, **kwargs)

        # Generate permanent code after save (when we have an id)
        if self.code.startswith("TEMP_"):
            self.code = generate_sales_revenue_code(self)
            super().save(update_fields=["code"])

    def reset_status_to_not_calculated(self):
        """Reset status to NOT_CALCULATED (used when editing)."""
        self.status = self.SalesRevenueStatus.NOT_CALCULATED
        self.save(update_fields=["status"])
