import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs import ColorVariant
from libs.models import BaseModel, ColoredValueMixin, SafeTextField


def generate_travel_expense_code(instance: "TravelExpense") -> str:
    """Generate travel expense code in format TE-{YYYYMM}-{seq}.

    Args:
        instance: TravelExpense instance which MUST have an id and month.

    Returns:
        Generated code string (e.g., "TE-202511-0001")

    Raises:
        ValueError: If the instance has no id or month.
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("TravelExpense must have an id to generate code")

    if not instance.month:
        raise ValueError("TravelExpense must have a month to generate code")

    year = instance.month.year
    month = instance.month.month
    month_key = f"{year}{month:02d}"

    max_code = (
        TravelExpense.objects.filter(month=instance.month, code__startswith=f"TE-{month_key}-")
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
    return f"TE-{month_key}-{seq:04d}"


@audit_logging_register
class TravelExpense(ColoredValueMixin, BaseModel):
    """Travel expense model for tracking employee travel expenses.

    This model stores travel expense information with automatic code generation,
    payroll status tracking, and support for both taxable and non-taxable expenses.

    Attributes:
        id: Auto-increment primary key
        code: Auto-generated unique code in format TE-{YYYYMM}-{seq}
        name: Expense description (max 250 characters)
        expense_type: Type of expense (TAXABLE or NON_TAXABLE)
        employee: Foreign key to Employee model
        amount: Expense amount in VND (integer, must be positive)
        month: Month as first day of the month
        status: Payroll calculation status (NOT_CALCULATED or CALCULATED)
        note: Additional notes (max 500 characters, sanitized HTML)
        created_at/updated_at: Audit timestamps
        created_by/updated_by: Audit user references
    """

    CODE_PREFIX = "TE"

    class ExpenseType(models.TextChoices):
        TAXABLE = "TAXABLE", "Taxable"
        NON_TAXABLE = "NON_TAXABLE", "Non-taxable"
        BY_WORKING_DAYS = "BY_WORKING_DAYS", "By working days"

    class TravelExpenseStatus(models.TextChoices):
        NOT_CALCULATED = "NOT_CALCULATED", "Not calculated"
        CALCULATED = "CALCULATED", "Calculated"

    VARIANT_MAPPING = {
        "status": {
            TravelExpenseStatus.NOT_CALCULATED: ColorVariant.GREY,
            TravelExpenseStatus.CALCULATED: ColorVariant.RED,
        }
    }

    code = models.CharField(max_length=50, unique=True, editable=False, db_index=True, verbose_name=_("Code"))
    name = models.CharField(max_length=250, verbose_name=_("Expense name"))
    expense_type = models.CharField(max_length=20, choices=ExpenseType.choices, verbose_name=_("Expense type"))
    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="travel_expenses",
        verbose_name=_("Employee"),
    )
    amount = models.IntegerField(validators=[MinValueValidator(1)], verbose_name=_("Amount"))
    month = models.DateField(db_index=True, help_text=_("First day of the expense month"), verbose_name=_("Month"))
    status = models.CharField(
        max_length=20,
        choices=TravelExpenseStatus.choices,
        default=TravelExpenseStatus.NOT_CALCULATED,
        db_index=True,
        editable=False,
        verbose_name=_("Status"),
    )
    note = SafeTextField(max_length=500, blank=True, default="", verbose_name=_("Note"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="travel_expenses_created",
        verbose_name=_("Created by"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="travel_expenses_updated",
        verbose_name=_("Updated by"),
    )

    class Meta:
        verbose_name = _("Travel Expense")
        verbose_name_plural = _("Travel Expenses")
        db_table = "payroll_travel_expense"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["month", "expense_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

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
            self.code = generate_travel_expense_code(self)
            super().save(update_fields=["code"])

    def delete(self, *args, **kwargs):
        """Prevent deletion if status is CALCULATED."""
        if self.status == self.TravelExpenseStatus.CALCULATED:
            raise ValidationError(
                _("Cannot delete travel expense that has been calculated. Status: %(status)s")
                % {"status": self.get_status_display()}
            )
        return super().delete(*args, **kwargs)

    def reset_status_to_not_calculated(self):
        """Reset status to NOT_CALCULATED (used when editing)."""
        self.status = self.TravelExpenseStatus.NOT_CALCULATED
        self.save(update_fields=["status"])
