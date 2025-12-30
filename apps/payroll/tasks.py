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

        try:
            plain_message = render_to_string("emails/payroll_slip.txt", context)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to render payroll slip text template for employee {employee.code}: {str(e)}")
            # Fallback to simple message if text template fails
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


@shared_task(bind=True)
def create_salary_period_task(self, month_str, proposal_deadline_str=None, kpi_assessment_deadline_str=None):
    """Create salary period and generate all payroll slips asynchronously.

    Args:
        self: Task instance (bind=True)
        month_str: Month in YYYY-MM format
        proposal_deadline_str: Optional proposal deadline (YYYY-MM-DD)
        kpi_assessment_deadline_str: Optional KPI assessment deadline (YYYY-MM-DD)

    Returns:
        dict: Result with period_id and statistics
    """
    from datetime import date

    from apps.hrm.models import Employee
    from apps.payroll.models import PayrollSlip, SalaryConfig, SalaryPeriod
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

    try:
        # Parse month (YYYY-MM format)
        year, month = map(int, month_str.split("-"))
        target_month = date(year, month, 1)

        # Parse deadlines if provided
        proposal_deadline = date.fromisoformat(proposal_deadline_str) if proposal_deadline_str else None
        kpi_assessment_deadline = (
            date.fromisoformat(kpi_assessment_deadline_str) if kpi_assessment_deadline_str else None
        )

        # Get latest salary config
        salary_config = SalaryConfig.objects.first()
        if not salary_config:
            return {"error": "No salary configuration found"}

        # Create salary period
        salary_period = SalaryPeriod.objects.create(
            month=target_month,
            salary_config_snapshot=salary_config.config,
            proposal_deadline=proposal_deadline,
            kpi_assessment_deadline=kpi_assessment_deadline,
        )

        # Get employees to create payroll slips for
        active_employees = Employee.objects.exclude(status=Employee.Status.RESIGNED)
        resigned_in_period = Employee.objects.filter(
            status=Employee.Status.RESIGNED,
            resignation_start_date__year=target_month.year,
            resignation_start_date__month=target_month.month,
        )
        employees = active_employees | resigned_in_period

        created_count = 0
        for employee in employees:
            # Update task state for progress tracking
            self.update_state(
                state="PROGRESS",
                meta={"current": created_count, "total": employees.count(), "status": "Creating payroll slips"},
            )

            payroll_slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee)
            # Calculate payroll immediately
            calculator = PayrollCalculationService(payroll_slip)
            calculator.calculate()
            created_count += 1

        # Update employee count and statistics
        salary_period.total_employees = created_count
        salary_period.save(update_fields=["total_employees"])
        salary_period.update_statistics()

        return {
            "period_id": salary_period.id,
            "period_code": salary_period.code,
            "total_employees": created_count,
            "status": "completed",
        }

    except Exception as e:
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        return {"error": str(e)}


@shared_task(bind=True)
def recalculate_salary_period_task(self, period_id):
    """Recalculate all payroll slips in a salary period asynchronously.

    Args:
        self: Task instance (bind=True)
        period_id: SalaryPeriod ID

    Returns:
        dict: Result with statistics
    """
    from apps.payroll.models import SalaryPeriod
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

    try:
        salary_period = SalaryPeriod.objects.get(pk=period_id)

        if salary_period.status == SalaryPeriod.Status.COMPLETED:
            return {"error": "Cannot recalculate completed period"}

        payroll_slips = salary_period.payroll_slips.all()
        total = payroll_slips.count()
        recalculated_count = 0

        for slip in payroll_slips:
            # Update task state for progress tracking
            self.update_state(
                state="PROGRESS",
                meta={"current": recalculated_count, "total": total, "status": "Recalculating payroll slips"},
            )

            calculator = PayrollCalculationService(slip)
            calculator.calculate()
            recalculated_count += 1

        # Update statistics
        salary_period.update_statistics()

        return {
            "period_id": salary_period.id,
            "period_code": salary_period.code,
            "recalculated_count": recalculated_count,
            "status": "completed",
        }

    except Exception as e:
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        return {"error": str(e)}


@shared_task(bind=True)
def send_emails_for_period_task(self, period_id, filter_status=None):
    """Send payroll emails for all slips in a period asynchronously.

    Args:
        self: Task instance (bind=True)
        period_id: SalaryPeriod ID
        filter_status: List of status values to filter slips (default: ["READY", "DELIVERED"])

    Returns:
        dict: Result with sent/failed counts
    """
    from apps.payroll.models import PayrollSlip, SalaryPeriod

    try:
        salary_period = SalaryPeriod.objects.get(pk=period_id)

        # Default filter status
        if filter_status is None:
            filter_status = [PayrollSlip.Status.READY, PayrollSlip.Status.DELIVERED]

        # Get slips to send emails
        slips = salary_period.payroll_slips.filter(status__in=filter_status, employee__email__isnull=False).exclude(
            employee__email=""
        )

        total = slips.count()
        sent_count = 0
        failed_count = 0
        failed_emails = []

        for slip in slips:
            # Update task state for progress tracking
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": sent_count + failed_count,
                    "total": total,
                    "status": "Sending payroll emails",
                    "sent": sent_count,
                    "failed": failed_count,
                },
            )

            # Call individual email task synchronously
            result = send_payroll_email_task(slip.id)

            if "Failed" in result or "not found" in result or "no email" in result:
                failed_count += 1
                failed_emails.append(
                    {"employee_code": slip.employee_code, "employee_email": slip.employee.email, "error": result}
                )
            else:
                sent_count += 1

        return {
            "period_id": salary_period.id,
            "period_code": salary_period.code,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "failed_emails": failed_emails,
            "status": "completed",
        }

    except Exception as e:
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        return {"error": str(e)}
