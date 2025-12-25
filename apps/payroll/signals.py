"""Signals for payroll app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    PenaltyTicket,
    RecoveryVoucher,
    SalesRevenue,
)
from apps.payroll.utils import update_department_assessment_status
from libs.code_generation import register_auto_code_signal


@receiver(post_save, sender=EmployeeKPIAssessment)
def update_department_status_on_employee_assessment_save(sender, instance, **kwargs):
    """Update department assessment status when employee assessment is saved.

    This signal triggers when an EmployeeKPIAssessment is saved and:
    1. Finds the corresponding DepartmentKPIAssessment
    2. Recalculates is_finished (all employees graded)
    3. Recalculates is_valid_unit_control if finished
    """
    # Only update if employee has a department
    if not instance.employee or not instance.employee.department:
        return

    # Find corresponding department assessment
    try:
        dept_assessment = DepartmentKPIAssessment.objects.get(
            period=instance.period, department=instance.employee.department
        )
    except DepartmentKPIAssessment.DoesNotExist:
        # No department assessment exists yet
        return

    # Update department status
    update_department_assessment_status(dept_assessment)


"""Signal handlers for Payroll app."""


def generate_sales_revenue_code(instance: SalesRevenue) -> str:
    """Generate sales revenue code in format SR-{YYYYMM}-{seq}.

    Args:
        instance: SalesRevenue instance which MUST have an id and month.

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
        SalesRevenue.objects.filter(month=instance.month, code__startswith=f"{SalesRevenue.CODE_PREFIX}-{month_key}-")
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
    return f"{SalesRevenue.CODE_PREFIX}-{month_key}-{seq:04d}"


register_auto_code_signal(
    SalesRevenue,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_sales_revenue_code,
)


def generate_recovery_voucher_code(instance: RecoveryVoucher) -> str:
    """Generate and assign code for RecoveryVoucher in format RV-{YYYYMM}-{seq}.

    Args:
        instance: RecoveryVoucher instance with month set

    Raises:
        ValueError: If month is not set on the instance
    """
    if not instance.month:
        raise ValueError("Month must be set to generate code")

    year_month = instance.month.strftime("%Y%m")
    prefix = f"{RecoveryVoucher.CODE_PREFIX}-{year_month}-"

    # Find existing codes for this month (excluding current instance if any)
    existing_codes = (
        RecoveryVoucher.objects.filter(code__startswith=prefix).exclude(pk=instance.pk).values_list("code", flat=True)
    )

    max_seq = 0
    for code in existing_codes:
        try:
            seq_part = code.split("-")[-1]
            seq = int(seq_part)
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    next_seq = max_seq + 1
    return f"{prefix}{str(next_seq).zfill(4)}"


register_auto_code_signal(
    RecoveryVoucher,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_recovery_voucher_code,
)


def generate_penalty_ticket_code(instance: "PenaltyTicket") -> str:
    """Generate and assign a code for a PenaltyTicket instance.

    Format: RVF-{YYYYMM}-{seq}
    Example: RVF-202511-0001

    Args:
        instance: PenaltyTicket instance which MUST have a non-None id and month

    Raises:
        ValueError: If the instance has no id set or month missing
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("PenaltyTicket must have an id to generate code")

    if not instance.month:
        raise ValueError("PenaltyTicket must have a month to generate code")

    month_str = instance.month.strftime("%Y%m")
    seq = str(instance.id).zfill(4)

    return f"{PenaltyTicket.CODE_PREFIX}-{month_str}-{seq}"


register_auto_code_signal(
    PenaltyTicket,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_penalty_ticket_code,
)
