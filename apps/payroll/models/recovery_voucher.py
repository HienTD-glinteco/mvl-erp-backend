from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.models import Employee
from libs import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField


@audit_logging_register
class RecoveryVoucher(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Recovery or Back Pay voucher model for payroll adjustments.

    This model represents recovery (deduction) or back pay (addition) vouchers
    that adjust employee payroll for a specific period.

    Attributes:
        code: Unique voucher code in format RV-{YYYYMM}-{seq}
        name: Descriptive name for the voucher
        voucher_type: Type of voucher (RECOVERY or BACK_PAY)
        employee: Reference to the employee this voucher applies to
        employee_code: Cached employee code for search performance
        employee_name: Cached employee name for search performance
        amount: Amount in Vietnamese Dong (stored as integer)
        month: Period stored as the first day of the month
        status: Calculation status (NOT_CALCULATED or CALCULATED)
        note: Optional notes about the voucher
    """

    class VoucherType(models.TextChoices):
        RECOVERY = "RECOVERY", _("Recovery")
        BACK_PAY = "BACK_PAY", _("Back Pay")

    class RecoveryVoucherStatus(models.TextChoices):
        NOT_CALCULATED = "NOT_CALCULATED", _("Not Calculated")
        CALCULATED = "CALCULATED", _("Calculated")

    VARIANT_MAPPING = {
        "status": {
            RecoveryVoucherStatus.NOT_CALCULATED: ColorVariant.GREY,
            RecoveryVoucherStatus.CALCULATED: ColorVariant.GREEN,
        }
    }

    code = models.CharField(max_length=50, unique=True, verbose_name=_("Voucher Code"))
    name = models.CharField(max_length=250, verbose_name=_("Name"))
    voucher_type = models.CharField(
        max_length=20,
        choices=VoucherType.choices,
        verbose_name=_("Voucher Type"),
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="recovery_vouchers",
        verbose_name=_("Employee"),
    )
    employee_code = models.CharField(max_length=50, verbose_name=_("Employee Code"))
    employee_name = models.CharField(max_length=250, verbose_name=_("Employee Name"))
    amount = models.IntegerField(verbose_name=_("Amount (VND)"))
    month = models.DateField(verbose_name=_("Month"))
    status = models.CharField(
        max_length=20,
        choices=RecoveryVoucherStatus.choices,
        default=RecoveryVoucherStatus.NOT_CALCULATED,
        verbose_name=_("Status"),
    )
    note = SafeTextField(max_length=500, blank=True, verbose_name=_("Note"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_recovery_vouchers",
        verbose_name=_("Created By"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_recovery_vouchers",
        verbose_name=_("Updated By"),
    )

    class Meta:
        verbose_name = _("Recovery Voucher")
        verbose_name_plural = _("Recovery Vouchers")
        db_table = "payroll_recovery_voucher"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["month", "employee"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-updated_at"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def colored_status(self):
        return self.get_colored_value("status")

    def clean(self):
        """Validate model fields."""
        super().clean()
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": _("Amount must be greater than 0.")})

    def save(self, *args, **kwargs):
        """Override save to cache employee fields and run validations."""
        # Cache employee fields for search
        if self.employee:
            self.employee_code = self.employee.code
            self.employee_name = self.employee.fullname

        # Run clean before saving

        self.clean()
        super().save(*args, **kwargs)
