"""PayrollSlip model for individual employee payroll calculations."""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin


def generate_payroll_slip_code(instance, force_save: bool = True) -> None:
    """Generate code for PayrollSlip in format PS_YYYYMM_ID.

    Args:
        instance: PayrollSlip instance
        force_save: If True, save the instance after setting code
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("PayrollSlip must have an id to generate code")

    month_str = instance.salary_period.month.strftime("%Y%m")
    instance_id = str(instance.id).zfill(4)
    code = f"PS_{month_str}_{instance_id}"
    instance.code = code

    if force_save:
        instance.save(update_fields=["code"])


@audit_logging_register
class PayrollSlip(AutoCodeMixin, ColoredValueMixin, BaseModel):
    """Payroll slip model representing individual employee salary calculation for a period.

    This model stores comprehensive salary calculation including contract details,
    KPI assessment, sales performance, overtime, travel expenses, insurance contributions,
    personal income tax, and recovery vouchers.

    Attributes:
        code: Unique code in format PS-YYYYMM-NNNN
        salary_period: Reference to salary period
        employee: Reference to employee
        status: Slip status (PENDING, READY, HOLD, DELIVERED)
        All salary calculation fields as documented in the SRS
    """

    class Status(models.TextChoices):
        """Status choices for payroll slip."""

        PENDING = "PENDING", _("Pending")
        READY = "READY", _("Ready")
        HOLD = "HOLD", _("Hold")
        DELIVERED = "DELIVERED", _("Delivered")

    CODE_PREFIX = "PS"

    VARIANT_MAPPING = {
        "status": {
            Status.PENDING: ColorVariant.YELLOW,
            Status.READY: ColorVariant.GREEN,
            Status.HOLD: ColorVariant.RED,
            Status.DELIVERED: ColorVariant.BLUE,
        }
    }

    # ========== Basic Information ==========
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Code"))

    salary_period = models.ForeignKey(
        "SalaryPeriod", on_delete=models.CASCADE, related_name="payroll_slips", verbose_name=_("Salary Period")
    )

    # Payment period - when this slip is actually paid (may differ from salary_period)
    payment_period = models.ForeignKey(
        "SalaryPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_slips",
        verbose_name=_("Payment Period"),
        help_text="The period when this slip is actually paid (may differ from salary_period)",
    )

    employee = models.ForeignKey(
        "hrm.Employee", on_delete=models.PROTECT, related_name="payroll_slips", verbose_name=_("Employee")
    )

    # Cached employee information
    employee_code = models.CharField(max_length=50, verbose_name=_("Employee Code"))
    employee_name = models.CharField(max_length=250, verbose_name=_("Employee Name"))
    employee_email = models.EmailField(max_length=254, blank=True, default="", verbose_name=_("Employee Email"))
    tax_code = models.CharField(max_length=20, blank=True, default="", verbose_name=_("Tax Code"))
    department_name = models.CharField(max_length=250, verbose_name=_("Department Name"))
    position_name = models.CharField(max_length=250, verbose_name=_("Position Name"))
    employment_status = models.CharField(max_length=20, verbose_name=_("Employment Status"))
    employee_official_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Employee Official Date"),
        help_text="Date when employee became OFFICIAL, used for insurance calculation",
    )

    # Penalty ticket flags
    has_unpaid_penalty = models.BooleanField(
        default=False, verbose_name=_("Has Unpaid Penalty"), help_text="Flag if employee has unpaid penalty tickets"
    )
    unpaid_penalty_count = models.IntegerField(
        default=0, verbose_name=_("Unpaid Penalty Count"), help_text="Count of unpaid penalty tickets"
    )

    # ========== Contract Information ==========
    contract_id = models.UUIDField(null=True, blank=True, verbose_name=_("Contract ID"))

    base_salary = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name=_("Base Salary"))

    kpi_salary = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name=_("KPI Salary"))

    lunch_allowance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Lunch Allowance")
    )

    phone_allowance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Phone Allowance")
    )

    other_allowance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Other Allowance")
    )

    # ========== KPI Component ==========
    kpi_grade = models.CharField(max_length=10, default="C", verbose_name=_("KPI Grade"))

    kpi_percentage = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0000"), verbose_name=_("KPI Percentage")
    )

    kpi_bonus = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name=_("KPI Bonus"))

    # ========== Sales Performance ==========
    sales_revenue = models.BigIntegerField(default=0, verbose_name=_("Sales Revenue"))

    sales_transaction_count = models.IntegerField(default=0, verbose_name=_("Sales Transaction Count"))

    business_grade = models.CharField(max_length=10, default="M0", verbose_name=_("Business Grade"))

    business_progressive_salary = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Business Progressive Salary")
    )

    # ========== Working Days ==========
    standard_working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Standard Working Days")
    )

    total_working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Total Working Days")
    )

    official_working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Official Working Days")
    )

    probation_working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Probation Working Days")
    )

    # ========== Overtime ==========
    tc1_overtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name=_("TC1 Overtime Hours (Weekday & Sat)")
    )

    tc2_overtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name=_("TC2 Overtime Hours (Sunday)")
    )

    tc3_overtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name=_("TC3 Overtime Hours (Holiday)")
    )

    total_overtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Total Overtime Hours")
    )

    hourly_rate = models.DecimalField(
        max_digits=20, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Hourly Rate")
    )

    overtime_pay = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name=_("Overtime Pay"))

    # ========== New Salary Calculation Fields ==========
    total_position_income = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Total Position Income")
    )

    actual_working_days_income = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Actual Working Days Income")
    )

    taxable_overtime_salary = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Taxable Overtime Salary")
    )

    overtime_progress_allowance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Overtime Progress Allowance")
    )

    non_taxable_overtime_salary = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Non-Taxable Overtime Salary")
    )

    # ========== Travel Expenses ==========
    taxable_travel_expense = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Taxable Travel Expense")
    )

    non_taxable_travel_expense = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Non-Taxable Travel Expense")
    )

    travel_expense_by_working_days = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Travel Expense By Working Days")
    )

    total_travel_expense = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Total Travel Expense")
    )

    # ========== Income Calculation ==========
    gross_income = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name=_("Gross Income"))

    taxable_income_base = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Taxable Income Base")
    )

    # ========== Insurance (Employee) ==========
    social_insurance_base = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Social Insurance Base")
    )

    employee_social_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employee Social Insurance")
    )

    employee_health_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employee Health Insurance")
    )

    employee_unemployment_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employee Unemployment Insurance")
    )

    employee_union_fee = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employee Union Fee")
    )

    # ========== Insurance (Employer) ==========
    employer_social_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employer Social Insurance")
    )

    employer_health_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employer Health Insurance")
    )

    employer_unemployment_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employer Unemployment Insurance")
    )

    employer_union_fee = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employer Union Fee")
    )

    employer_accident_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Employer Accident Insurance")
    )

    # ========== Personal Income Tax ==========
    personal_deduction = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Personal Deduction")
    )

    dependent_count = models.IntegerField(default=0, verbose_name=_("Dependent Count"))

    dependent_deduction = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Dependent Deduction")
    )

    total_family_deduction = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Total Family Deduction")
    )

    non_taxable_allowance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Non-Taxable Allowance")
    )

    taxable_income = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name=_("Taxable Income"))

    personal_income_tax = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Personal Income Tax")
    )

    # ========== Recovery Vouchers ==========
    back_pay_amount = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Back Pay Amount")
    )

    recovery_amount = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name=_("Recovery Amount")
    )

    # ========== Final Calculation ==========
    net_salary = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name=_("Net Salary"))

    # ========== Workflow & Status ==========
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True, verbose_name=_("Status")
    )

    status_note = models.TextField(
        blank=True, verbose_name=_("Status Note"), help_text="Reason for PENDING or HOLD status"
    )

    need_resend_email = models.BooleanField(
        default=True, db_index=True, verbose_name=_("Need Resend Email"), help_text="Flag if email needs to be resent"
    )

    email_sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Email Sent At"))

    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Delivered At"))

    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivered_payroll_slips",
        verbose_name=_("Delivered By"),
    )

    # ========== Hold Tracking Fields ==========
    hold_reason = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Hold Reason"),
        help_text="Reason for holding the salary",
    )

    held_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Held At"), help_text="Timestamp when slip was put on hold"
    )

    held_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="held_payroll_slips",
        verbose_name=_("Held By"),
    )

    # ========== Audit Fields ==========
    calculation_log = models.JSONField(
        default=dict, verbose_name=_("Calculation Log"), help_text="Detailed breakdown of calculation"
    )

    calculated_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Calculated At"))

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payroll_slips",
        verbose_name=_("Created By"),
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_payroll_slips",
        verbose_name=_("Updated By"),
    )

    class Meta:
        verbose_name = _("Payroll Slip")
        verbose_name_plural = _("Payroll Slips")
        db_table = "payroll_payroll_slip"
        ordering = ["-calculated_at"]
        constraints = [
            models.UniqueConstraint(fields=["salary_period", "employee"], name="unique_salary_period_employee")
        ]
        indexes = [
            models.Index(fields=["salary_period", "status"], name="payroll_slip_period_status_idx"),
            models.Index(fields=["employee"], name="payroll_slip_employee_idx"),
            models.Index(fields=["status"], name="payroll_slip_status_idx"),
            models.Index(fields=["need_resend_email"], name="payroll_slip_resend_idx"),
            models.Index(fields=["-calculated_at"], name="payroll_slip_calculated_idx"),
        ]

    def __str__(self):
        return f"{self.code} - {self.employee_code} - {self.salary_period.month.strftime('%Y-%m')}"

    @property
    def colored_status(self):
        """Get colored value representation for status field."""
        return self.get_colored_value("status")

    @property
    def is_carried_over(self) -> bool:
        """Check if slip is being paid in a different period than it belongs to.

        Returns True if payment_period differs from salary_period.
        This happens when a slip becomes READY after its period was COMPLETED
        (e.g., after penalty payment) and will be paid in a later period.
        """
        return self.payment_period_id is not None and self.payment_period_id != self.salary_period_id

    def hold(self, reason: str, user=None):
        """Put payroll slip on hold.

        Business Rules:
        1. Any status except HOLD can be held
        2. Status changes to HOLD
        3. Reason is required

        Args:
            reason: Reason for holding
            user: User performing the hold

        Raises:
            ValidationError: If hold is not allowed
        """
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        if self.status == self.Status.HOLD:
            raise ValidationError("Slip is already on HOLD")

        if not reason:
            raise ValidationError("Hold reason is required")

        self.status = self.Status.HOLD
        self.hold_reason = reason
        self.status_note = f"Hold: {reason}"
        self.held_at = timezone.now()
        self.held_by = user
        self.save(update_fields=["status", "hold_reason", "status_note", "held_at", "held_by", "updated_at"])

    def unhold(self, user=None):
        """Release held payroll slip.

        Business Rules:
        1. Only HOLD slips can be unholded
        2. Triggers recalculation
        3. Status determined by recalculation (READY or PENDING)
        4. If salary period is ONGOING: slip goes to Table 1
        5. If salary period is COMPLETED:
           - Slip stays in Table 2 of old period
           - AND appears in Table 1 of current ONGOING period

        Args:
            user: User performing the unhold

        Raises:
            ValidationError: If unhold is not allowed
        """
        from django.core.exceptions import ValidationError

        if self.status != self.Status.HOLD:
            raise ValidationError(f"Cannot unhold slip with status {self.status}")

        # Clear hold info
        self.hold_reason = ""
        self.status_note = ""
        self.held_at = None
        self.held_by = None

        self._recalculate_and_update_status()

        self.save()

    def _recalculate_and_update_status(self):
        """Recalculate and determine new status."""
        from apps.payroll.services.payroll_calculation import PayrollCalculationService

        calculator = PayrollCalculationService(self)
        calculator.calculate()
        # Status is determined by calculator._determine_final_status()
