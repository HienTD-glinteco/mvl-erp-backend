"""Celery tasks for payroll app."""

from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def recalculate_payroll_slip_task(employee_id, month_str):
    """Recalculate a single payroll slip asynchronously.

    Args:
        employee_id: Employee ID (UUID as string)
        month_str: Month as ISO format string (YYYY-MM-DD)

    Returns:
        str: Result message
    """
    from apps.payroll.models import PayrollSlip, SalaryPeriod
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

    # Parse month
    month = date.fromisoformat(month_str)

    # Get salary period
    try:
        salary_period = SalaryPeriod.objects.get(month=month)
    except SalaryPeriod.DoesNotExist:
        return f"No salary period for {month}"

    if salary_period.status == SalaryPeriod.Status.COMPLETED:
        return f"Salary period {month} is completed, cannot recalculate"

    # Get or create payroll slip
    try:
        payroll_slip = PayrollSlip.objects.get(salary_period=salary_period, employee_id=employee_id)
    except PayrollSlip.DoesNotExist:
        return f"No payroll slip for employee {employee_id} in period {month}"

    # Calculate
    calculator = PayrollCalculationService(payroll_slip)
    calculator.calculate()

    # Set need_resend_email if value changed
    payroll_slip.need_resend_email = True
    payroll_slip.save(update_fields=["need_resend_email"])

    return f"Recalculated payroll for employee {employee_id}, month {month}"


@shared_task
def recalculate_salary_period_task(salary_period_id):
    """Recalculate all payroll slips in a salary period asynchronously.

    Args:
        salary_period_id: SalaryPeriod ID

    Returns:
        str: Result message
    """
    from apps.payroll.models import SalaryPeriod

    try:
        salary_period = SalaryPeriod.objects.get(pk=salary_period_id)
    except SalaryPeriod.DoesNotExist:
        return f"Salary period {salary_period_id} not found"

    if salary_period.status == SalaryPeriod.Status.COMPLETED:
        return "Salary period is completed, cannot recalculate"

    payroll_slips = salary_period.payroll_slips.all()

    success_count = 0
    failed_count = 0

    for slip in payroll_slips:
        try:
            recalculate_payroll_slip_task.delay(str(slip.employee_id), slip.salary_period.month.isoformat())
            success_count += 1
        except Exception:
            failed_count += 1

    return f"Queued {success_count} recalculations, {failed_count} failed"


@shared_task
def auto_generate_salary_period():
    """Auto-generate next month's salary period on last day of month.

    This task should be scheduled to run daily at 23:00 on days 28-31.
    It will only create a period if today is the last day of the month.

    Returns:
        str: Result message
    """
    from apps.hrm.models import Employee
    from apps.payroll.models import PayrollSlip, SalaryConfig, SalaryPeriod

    today = date.today()

    # Check if today is last day of month
    tomorrow = today + timedelta(days=1)
    if tomorrow.month == today.month:
        # Not last day of month
        return "Not last day of month"

    # Today is last day of month, generate next month period
    next_month = tomorrow.replace(day=1)

    # Check if already exists
    if SalaryPeriod.objects.filter(month=next_month).exists():
        return f"Salary period for {next_month} already exists"

    # Check previous period is completed
    previous_periods = SalaryPeriod.objects.filter(month__lt=next_month).order_by("-month")

    if previous_periods.exists() and previous_periods.first().status != SalaryPeriod.Status.COMPLETED:
        return f"Previous period {previous_periods.first().month} is not completed yet"

    # Get latest salary config
    salary_config = SalaryConfig.objects.first()
    if not salary_config:
        return "No salary configuration found"

    # Create new period
    salary_period = SalaryPeriod.objects.create(
        month=next_month, salary_config_snapshot=salary_config.config, created_by=None
    )

    # Create payroll slips for all active employees
    active_employees = Employee.objects.filter(is_active=True)

    for employee in active_employees:
        PayrollSlip.objects.create(salary_period=salary_period, employee=employee)

    # Update employee count
    salary_period.total_employees = active_employees.count()
    salary_period.save(update_fields=["total_employees"])

    return f"Created salary period for {next_month} with {active_employees.count()} employees"


@shared_task
def send_payroll_email_task(payroll_slip_id):
    """Send payroll notification email to employee asynchronously.

    Args:
        payroll_slip_id: PayrollSlip ID

    Returns:
        str: Result message
    """
    from apps.payroll.models import PayrollSlip

    try:
        payroll_slip = PayrollSlip.objects.get(pk=payroll_slip_id)
    except PayrollSlip.DoesNotExist:
        return f"Payroll slip {payroll_slip_id} not found"

    # TODO: Implement actual email sending
    # For now, just mark as sent
    payroll_slip.email_sent_at = timezone.now()
    payroll_slip.need_resend_email = False
    payroll_slip.save(update_fields=["email_sent_at", "need_resend_email"])

    return f"Email sent to {payroll_slip.employee.email}"
