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
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")

    salary_period = models.ForeignKey(
        "SalaryPeriod", on_delete=models.CASCADE, related_name="payroll_slips", verbose_name="Salary Period"
    )

    employee = models.ForeignKey(
        "hrm.Employee", on_delete=models.PROTECT, related_name="payroll_slips", verbose_name="Employee"
    )

    # Cached employee information
    employee_code = models.CharField(max_length=50, verbose_name="Employee Code")
    employee_name = models.CharField(max_length=250, verbose_name="Employee Name")
    department_name = models.CharField(max_length=250, verbose_name="Department Name")
    position_name = models.CharField(max_length=250, verbose_name="Position Name")
    employment_status = models.CharField(max_length=20, verbose_name="Employment Status")

    # Penalty ticket flags
    has_unpaid_penalty = models.BooleanField(
        default=False, verbose_name="Has Unpaid Penalty", help_text="Flag if employee has unpaid penalty tickets"
    )
    unpaid_penalty_count = models.IntegerField(
        default=0, verbose_name="Unpaid Penalty Count", help_text="Count of unpaid penalty tickets"
    )

    # ========== Contract Information ==========
    contract_id = models.UUIDField(null=True, blank=True, verbose_name="Contract ID")

    base_salary = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Base Salary")

    kpi_salary = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="KPI Salary")

    lunch_allowance = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Lunch Allowance")

    phone_allowance = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Phone Allowance")

    other_allowance = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Other Allowance")

    # ========== KPI Component ==========
    kpi_grade = models.CharField(max_length=10, default="C", verbose_name="KPI Grade")

    kpi_percentage = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0000"), verbose_name="KPI Percentage"
    )

    kpi_bonus = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="KPI Bonus")

    # ========== Sales Performance ==========
    sales_revenue = models.BigIntegerField(default=0, verbose_name="Sales Revenue")

    sales_transaction_count = models.IntegerField(default=0, verbose_name="Sales Transaction Count")

    business_grade = models.CharField(max_length=10, default="M0", verbose_name="Business Grade")

    business_progressive_salary = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Business Progressive Salary"
    )

    # ========== Working Days ==========
    standard_working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Standard Working Days"
    )

    total_working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Total Working Days"
    )

    official_working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Official Working Days"
    )

    probation_working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Probation Working Days"
    )

    # ========== Overtime ==========
    saturday_inweek_overtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name="Saturday & Weekday Overtime Hours"
    )

    sunday_overtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name="Sunday Overtime Hours"
    )

    holiday_overtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name="Holiday Overtime Hours"
    )

    total_overtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name="Total Overtime Hours"
    )

    hourly_rate = models.DecimalField(
        max_digits=20, decimal_places=2, default=Decimal("0.00"), verbose_name="Hourly Rate"
    )

    overtime_pay = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Overtime Pay")

    # ========== Travel Expenses ==========
    taxable_travel_expense = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Taxable Travel Expense"
    )

    non_taxable_travel_expense = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Non-Taxable Travel Expense"
    )

    total_travel_expense = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Total Travel Expense"
    )

    # ========== Income Calculation ==========
    gross_income = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Gross Income")

    taxable_income_base = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Taxable Income Base"
    )

    # ========== Insurance (Employee) ==========
    social_insurance_base = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Social Insurance Base"
    )

    employee_social_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employee Social Insurance"
    )

    employee_health_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employee Health Insurance"
    )

    employee_unemployment_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employee Unemployment Insurance"
    )

    employee_union_fee = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employee Union Fee"
    )

    # ========== Insurance (Employer) ==========
    employer_social_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employer Social Insurance"
    )

    employer_health_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employer Health Insurance"
    )

    employer_unemployment_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employer Unemployment Insurance"
    )

    employer_union_fee = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employer Union Fee"
    )

    employer_accident_insurance = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Employer Accident Insurance"
    )

    # ========== Personal Income Tax ==========
    personal_deduction = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Personal Deduction"
    )

    dependent_count = models.IntegerField(default=0, verbose_name="Dependent Count")

    dependent_deduction = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Dependent Deduction"
    )

    taxable_income = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Taxable Income")

    personal_income_tax = models.DecimalField(
        max_digits=20, decimal_places=0, default=0, verbose_name="Personal Income Tax"
    )

    # ========== Recovery Vouchers ==========
    back_pay_amount = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Back Pay Amount")

    recovery_amount = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Recovery Amount")

    # ========== Final Calculation ==========
    net_salary = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="Net Salary")

    # ========== Workflow & Status ==========
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True, verbose_name="Status"
    )

    status_note = models.TextField(
        blank=True, verbose_name="Status Note", help_text="Reason for PENDING or HOLD status"
    )

    need_resend_email = models.BooleanField(
        default=False, db_index=True, verbose_name="Need Resend Email", help_text="Flag if email needs to be resent"
    )

    email_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Email Sent At")

    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Delivered At")

    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivered_payroll_slips",
        verbose_name="Delivered By",
    )

    # ========== Audit Fields ==========
    calculation_log = models.JSONField(
        default=dict, verbose_name="Calculation Log", help_text="Detailed breakdown of calculation"
    )

    calculated_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Calculated At")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payroll_slips",
        verbose_name="Created By",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_payroll_slips",
        verbose_name="Updated By",
    )

    class Meta:
        verbose_name = "Payroll Slip"
        verbose_name_plural = "Payroll Slips"
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
