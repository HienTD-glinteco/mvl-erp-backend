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
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

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

    # Get employees to create payroll slips for
    # Include all employees except RESIGNED, and RESIGNED employees with resignation_start_date in this period
    active_employees = Employee.objects.exclude(status=Employee.Status.RESIGNED)
    resigned_in_period = Employee.objects.filter(
        status=Employee.Status.RESIGNED,
        resignation_start_date__year=next_month.year,
        resignation_start_date__month=next_month.month,
    )
    employees = active_employees | resigned_in_period

    created_count = 0
    for employee in employees:
        payroll_slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee)
        # Calculate payroll immediately
        calculator = PayrollCalculationService(payroll_slip)
        calculator.calculate()
        created_count += 1

    # Update employee count
    salary_period.total_employees = created_count
    salary_period.save(update_fields=["total_employees"])

    return f"Created salary period for {next_month} with {created_count} employees and calculated all payrolls"


@shared_task
def send_payroll_email_task(payroll_slip_id):
    """Send payroll notification email to employee asynchronously.

    Args:
        payroll_slip_id: PayrollSlip ID

    Returns:
        str: Result message
    """
    import logging

    import sentry_sdk
    from django.conf import settings
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.translation import gettext as _

    from apps.payroll.models import PayrollSlip

    logger = logging.getLogger(__name__)

    try:
        payroll_slip = PayrollSlip.objects.select_related("employee", "salary_period").get(pk=payroll_slip_id)
    except PayrollSlip.DoesNotExist:
        return f"Payroll slip {payroll_slip_id} not found"

    employee = payroll_slip.employee

    if not employee.email:
        return f"Employee {employee.code} has no email address"

    try:
        context = {
            "employee": employee,
            "payroll_slip": payroll_slip,
            "salary_period": payroll_slip.salary_period,
            "current_year": timezone.now().year,
        }

        try:
            html_message = render_to_string("emails/payroll_slip.html", context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render payroll slip email template for employee {employee.code}: {str(e)}")
            raise

        plain_message = _(
            """Hello %(employee_name)s,

Your payroll slip for %(month)s is ready.

Employee Code: %(employee_code)s
Department: %(department)s
Position: %(position)s

Gross Income: %(gross_income)s VND
Net Salary: %(net_salary)s VND

Please log in to the system to view full details.

Best regards,
MaiVietLand Team"""
        ) % {
            "employee_name": employee.fullname,
            "month": payroll_slip.salary_period.month.strftime("%B %Y"),
            "employee_code": payroll_slip.employee_code,
            "department": payroll_slip.department_name,
            "position": payroll_slip.position_name,
            "gross_income": f"{payroll_slip.gross_income:,.0f}",
            "net_salary": f"{payroll_slip.net_salary:,.0f}",
        }

        send_mail(
            subject=_("Payroll Slip %(month)s - MaiVietLand")
            % {"month": payroll_slip.salary_period.month.strftime("%m/%Y")},
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[employee.email],
            fail_silently=False,
        )

        payroll_slip.email_sent_at = timezone.now()
        payroll_slip.need_resend_email = False
        payroll_slip.save(update_fields=["email_sent_at", "need_resend_email"])

        logger.info(f"Payroll email sent successfully to employee {employee.code}")
        return f"Email sent to {employee.email}"

    except Exception as e:
        logger.error(f"Failed to send payroll email to employee {employee.code}: {str(e)}")
        sentry_sdk.capture_exception(e)
        return f"Failed to send email: {str(e)}"
