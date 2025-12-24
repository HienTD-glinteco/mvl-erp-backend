"""Signals for payroll app."""

from django.db.models import Max
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    RecoveryVoucher,
    SalesRevenue,
)
from apps.payroll.utils import update_department_assessment_status
from libs.code_generation import register_auto_code_signal


def generate_sales_revenue_code(instance: SalesRevenue) -> None:
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
    instance.code = f"SR-{month_key}-{seq:04d}"
    instance.save(update_fields=["code"])


register_auto_code_signal(
    SalesRevenue,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_sales_revenue_code,
)


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


def generate_recovery_voucher_code(instance: RecoveryVoucher) -> str:
    """Generate unique code for RecoveryVoucher in format RV-{YYYYMM}-{seq}.

    Args:
        instance: RecoveryVoucher instance with period set

    Returns:
        Generated code string (e.g., "RV-202509-0001")
    """
    if not instance.month:
        raise ValueError("Month must be set to generate code")

    # Get year and month from period
    year_month = instance.month.strftime("%Y%m")
    # Find the maximum sequence number for this year-month
    prefix = f"RV-{year_month}-"
    max_code = RecoveryVoucher.objects.filter(code__startswith=prefix).aggregate(max_code=Max("code"))["max_code"]

    if max_code:
        # Extract sequence number from the last code
        try:
            seq = int(max_code.split("-")[-1])
            next_seq = seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1

    # Format with 4-digit padding
    return f"{prefix}{str(next_seq).zfill(4)}"


@receiver(post_save, sender=RecoveryVoucher)
def auto_generate_recovery_voucher_code(sender, instance, created, **kwargs):
    """Auto-generate code for RecoveryVoucher when created.

    This signal handler generates a unique code for newly created vouchers.
    The code format is: RV-{YYYYMM}-{seq}

    Args:
        sender: The RecoveryVoucher model class
        instance: The RecoveryVoucher instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments from the signal
    """
    # Only generate code for new instances that have a temporary code
    if created and instance.code and instance.code.startswith("TEMP_"):
        instance.code = generate_recovery_voucher_code(instance)
        # Use update_fields to prevent triggering the signal again
        instance.save(update_fields=["code"])
