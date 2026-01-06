"""SalaryPeriod model for monthly salary periods."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin

from ..utils.salary_period import calculate_standard_working_days


def generate_salary_period_code(instance, force_save: bool = True) -> None:
    """Generate code for SalaryPeriod in format SP_YYYYMM.

    Args:
        instance: SalaryPeriod instance
        force_save: If True, save the instance after setting code
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("SalaryPeriod must have an id to generate code")

    code = f"SP_{instance.month.strftime('%Y%m')}"
    instance.code = code

    if force_save:
        instance.save(update_fields=["code"])


@audit_logging_register
class SalaryPeriod(AutoCodeMixin, ColoredValueMixin, BaseModel):
    """Salary period model representing a monthly salary calculation period.

    This model stores information about a salary period including the month,
    configuration snapshot, and employee count. Only one period per month is allowed.

    Attributes:
        code: Unique code in format SP-YYYYMM
        month: First day of the salary month
        salary_config_snapshot: Snapshot of SalaryConfig used for this period
        status: Period status (ONGOING or COMPLETED)
        standard_working_days: Total working days in the month
        total_employees: Count of employees in this period
        completed_at: Completion timestamp
        completed_by: User who completed the period
    """

    class Status(models.TextChoices):
        """Status choices for salary period."""

        ONGOING = "ONGOING", _("Ongoing")
        COMPLETED = "COMPLETED", _("Completed")

    CODE_PREFIX = "SP"

    VARIANT_MAPPING = {
        "status": {
            Status.ONGOING: ColorVariant.BLUE,
            Status.COMPLETED: ColorVariant.GREEN,
        }
    }

    code = models.CharField(
        max_length=50, unique=True, verbose_name=_("Code"), help_text="Unique code in format SP-YYYYMM"
    )

    month = models.DateField(
        unique=True, db_index=True, verbose_name=_("Month"), help_text="First day of the salary month"
    )

    salary_config_snapshot = models.JSONField(
        verbose_name=_("Salary Config Snapshot"), help_text="Snapshot of salary configuration for this period"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ONGOING,
        db_index=True,
        verbose_name=_("Status"),
        help_text="Current status of the period",
    )

    standard_working_days = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_("Standard Working Days"),
        help_text="Total working days in the month",
    )

    total_employees = models.PositiveIntegerField(
        default=0, verbose_name=_("Total Employees"), help_text="Count of employees with payroll slips in this period"
    )

    # Deadline fields
    proposal_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Proposal Deadline"),
        help_text="Deadline for submitting payroll-related proposals (default: 2nd of next month)",
    )

    kpi_assessment_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("KPI Assessment Deadline"),
        help_text="Deadline for KPI assessments (default: 5th of next month)",
    )

    # Statistics fields
    employees_need_recovery = models.PositiveIntegerField(
        default=0, verbose_name=_("Employees Need Recovery"), help_text="Count of employees with recovery vouchers"
    )

    employees_with_penalties = models.PositiveIntegerField(
        default=0, verbose_name=_("Employees With Penalties"), help_text="Count of employees with penalty tickets"
    )

    employees_paid_penalties = models.PositiveIntegerField(
        default=0, verbose_name=_("Employees Paid Penalties"), help_text="Count of employees who paid penalties"
    )

    employees_with_travel = models.PositiveIntegerField(
        default=0, verbose_name=_("Employees With Travel"), help_text="Count of employees with travel expenses"
    )

    employees_need_email = models.PositiveIntegerField(
        default=0, verbose_name=_("Employees Need Email"), help_text="Count of employees needing payroll email"
    )

    # Payroll slip aggregate statistics
    pending_count = models.PositiveIntegerField(
        default=0, verbose_name=_("Pending Count"), help_text="Count of payroll slips in PENDING status"
    )

    ready_count = models.PositiveIntegerField(
        default=0, verbose_name=_("Ready Count"), help_text="Count of payroll slips in READY status"
    )

    hold_count = models.PositiveIntegerField(
        default=0, verbose_name=_("Hold Count"), help_text="Count of payroll slips in HOLD status"
    )

    delivered_count = models.PositiveIntegerField(
        default=0, verbose_name=_("Delivered Count"), help_text="Count of payroll slips in DELIVERED status"
    )

    total_gross_income = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name=_("Total Gross Income"),
        help_text="Sum of gross income from all payroll slips",
    )

    total_net_salary = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name=_("Total Net Salary"),
        help_text="Sum of net salary from all payroll slips",
    )

    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Completed At"), help_text="Timestamp when period was completed"
    )

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_salary_periods",
        verbose_name=_("Completed By"),
        help_text="User who completed the period",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_salary_periods",
        verbose_name=_("Created By"),
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_salary_periods",
        verbose_name=_("Updated By"),
    )

    class Meta:
        verbose_name = _("Salary Period")
        verbose_name_plural = _("Salary Periods")
        db_table = "payroll_salary_period"
        ordering = ["-month"]
        indexes = [
            models.Index(fields=["month"], name="salary_period_month_idx"),
            models.Index(fields=["status"], name="salary_period_status_idx"),
            models.Index(fields=["-created_at"], name="salary_period_created_idx"),
        ]

    def __str__(self):
        return f"{self.code} - {self.month.strftime('%Y-%m')}"

    @property
    def colored_status(self):
        """Get colored value representation for status field."""
        return self.get_colored_value("status")

    def save(self, *args, **kwargs):
        """Override save to auto-generate code and calculate working days."""
        # Calculate standard working days if not set
        if not self.pk and not self.standard_working_days:
            self.standard_working_days = calculate_standard_working_days(self.month.year, self.month.month)

        # Set default deadlines if not provided (only on creation)
        if not self.pk:
            from dateutil.relativedelta import relativedelta

            # Default proposal deadline: 2nd of next month
            if not self.proposal_deadline:
                next_month = self.month + relativedelta(months=1)
                self.proposal_deadline = next_month.replace(day=2)

            # Default KPI assessment deadline: 5th of next month
            if not self.kpi_assessment_deadline:
                next_month = self.month + relativedelta(months=1)
                self.kpi_assessment_deadline = next_month.replace(day=5)

        super().save(*args, **kwargs)

    def can_complete(self) -> bool:
        """Check if period can be completed.

        A period can be completed if all payroll slips are in READY or DELIVERED status.

        Returns:
            bool: True if period can be completed
        """
        from .payroll_slip import PayrollSlip

        # Check if there are any slips not in READY or DELIVERED status
        blocking_slips = self.payroll_slips.exclude(
            status__in=[PayrollSlip.Status.READY, PayrollSlip.Status.DELIVERED]
        ).exists()

        return not blocking_slips

    def complete(self, user=None):
        """Complete the salary period.

        Marks period as completed and changes all READY slips to DELIVERED.
        Can be executed at any time without checking can_complete.

        Args:
            user: User completing the period
        """
        from django.utils import timezone

        from .payroll_slip import PayrollSlip

        # Update all READY slips to DELIVERED
        self.payroll_slips.filter(status=PayrollSlip.Status.READY).update(
            status=PayrollSlip.Status.DELIVERED, delivered_at=timezone.now(), delivered_by=user
        )

        # Mark period as completed
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])

    def update_statistics(self):
        """Update all statistics fields based on current payroll slips."""
        from django.db.models import Count, Q, Sum

        from apps.payroll.models import PenaltyTicket, RecoveryVoucher, TravelExpense

        # Count employees with recovery vouchers
        self.employees_need_recovery = (
            RecoveryVoucher.objects.filter(month=self.month, voucher_type=RecoveryVoucher.VoucherType.RECOVERY)
            .values("employee")
            .distinct()
            .count()
        )

        # Count employees with penalty tickets (any status)
        self.employees_with_penalties = (
            PenaltyTicket.objects.filter(month=self.month).values("employee").distinct().count()
        )

        # Count employees who paid penalties
        self.employees_paid_penalties = (
            PenaltyTicket.objects.filter(month=self.month, status=PenaltyTicket.Status.PAID)
            .values("employee")
            .distinct()
            .count()
        )

        # Count employees with travel expenses
        self.employees_with_travel = (
            TravelExpense.objects.filter(month=self.month).values("employee").distinct().count()
        )

        # Count employees needing email (need_resend_email = True)
        self.employees_need_email = self.payroll_slips.filter(need_resend_email=True).count()

        # Update payroll slip aggregate statistics
        from .payroll_slip import PayrollSlip

        stats = self.payroll_slips.aggregate(
            pending_count=Count("id", filter=Q(status=PayrollSlip.Status.PENDING)),
            ready_count=Count("id", filter=Q(status=PayrollSlip.Status.READY)),
            hold_count=Count("id", filter=Q(status=PayrollSlip.Status.HOLD)),
            delivered_count=Count("id", filter=Q(status=PayrollSlip.Status.DELIVERED)),
            total_gross_income=Sum("gross_income"),
            total_net_salary=Sum("net_salary"),
        )

        self.pending_count = stats["pending_count"] or 0
        self.ready_count = stats["ready_count"] or 0
        self.hold_count = stats["hold_count"] or 0
        self.delivered_count = stats["delivered_count"] or 0
        self.total_gross_income = stats["total_gross_income"] or 0
        self.total_net_salary = stats["total_net_salary"] or 0

        self.save(
            update_fields=[
                "employees_need_recovery",
                "employees_with_penalties",
                "employees_paid_penalties",
                "employees_with_travel",
                "employees_need_email",
                "pending_count",
                "ready_count",
                "hold_count",
                "delivered_count",
                "total_gross_income",
                "total_net_salary",
            ]
        )
