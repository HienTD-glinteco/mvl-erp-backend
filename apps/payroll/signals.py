"""Signals for payroll app."""

from django.db.models import Max
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.payroll.models import DepartmentKPIAssessment, EmployeeKPIAssessment, RecoveryVoucher
from apps.payroll.utils import update_department_assessment_status


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
