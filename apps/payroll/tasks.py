"""Celery tasks for payroll app."""

from datetime import date, timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.payroll.services.sales_revenue_report_aggregator import SalesRevenueReportAggregator


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
    """Auto-generate salary period for the previous month.

    This task should be scheduled to run on the first day of each month at 00:00.
    It generates the salary period for the previous month that just ended.

    Returns:
        str: Result message
    """
    from apps.hrm.models import Employee
    from apps.payroll.models import PayrollSlip, SalaryConfig, SalaryPeriod
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

    today = date.today()
    # Get the first day of current month, then subtract one day to get last day of previous month
    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    # Get the first day of previous month
    previous_month = last_day_previous_month.replace(day=1)

    # Check if already exists
    if SalaryPeriod.objects.filter(month=previous_month).exists():
        return f"Salary period for {previous_month} already exists"

    # Check previous period is completed (if any exists)
    previous_periods = SalaryPeriod.objects.filter(month__lt=previous_month).order_by("-month")

    if previous_periods.exists() and previous_periods.first().status != SalaryPeriod.Status.COMPLETED:
        return f"Previous period {previous_periods.first().month} is not completed yet"

    # Get latest salary config
    salary_config = SalaryConfig.objects.first()
    if not salary_config:
        return "No salary configuration found"

    # Create new period
    salary_period = SalaryPeriod.objects.create(
        month=previous_month, salary_config_snapshot=salary_config.config, created_by=None
    )

    # Get employees to create payroll slips for
    # Include employees with start_date <= last day of period month
    # Calculate last day of period month
    if previous_month.month == 12:
        first_day_next_month = previous_month.replace(year=previous_month.year + 1, month=1)
    else:
        first_day_next_month = previous_month.replace(month=previous_month.month + 1)
    last_day_of_month = first_day_next_month - timedelta(days=1)

    # Active employees with start_date <= last day of month
    active_employees = Employee.objects.exclude(status=Employee.Status.RESIGNED).filter(
        start_date__lte=last_day_of_month
    )
    # RESIGNED employees with resignation_start_date in this period
    resigned_in_period = Employee.objects.filter(
        status=Employee.Status.RESIGNED,
        resignation_start_date__year=previous_month.year,
        resignation_start_date__month=previous_month.month,
        start_date__lte=last_day_of_month,
    )
    employees = active_employees | resigned_in_period

    created_count = 0
    for employee in employees:
        payroll_slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee)
        # Calculate payroll immediately
        calculator = PayrollCalculationService(payroll_slip)
        calculator.calculate()
        created_count += 1

    # Update employee count and statistics
    salary_period.total_employees = created_count
    salary_period.save(update_fields=["total_employees"])
    salary_period.update_statistics()

    return f"Created salary period for {previous_month} with {created_count} employees and calculated all payrolls"


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
        # Calculate last day of period month
        if target_month.month == 12:
            first_day_next_month = target_month.replace(year=target_month.year + 1, month=1)
        else:
            first_day_next_month = target_month.replace(month=target_month.month + 1)
        last_day_of_month = first_day_next_month - timedelta(days=1)

        # Active employees with start_date <= last day of month
        active_employees = Employee.objects.exclude(status=Employee.Status.RESIGNED).filter(
            start_date__lte=last_day_of_month
        )
        # RESIGNED employees with resignation_start_date in this period
        resigned_in_period = Employee.objects.filter(
            status=Employee.Status.RESIGNED,
            resignation_start_date__year=target_month.year,
            resignation_start_date__month=target_month.month,
            start_date__lte=last_day_of_month,
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


@shared_task
def aggregate_sales_revenue_report_task():
    """Aggregate sales revenue data into flat report model in background.

    This task is triggered after sales revenue import completes via
    the on_import_complete callback hook.

    Returns:
        dict: Result with count of records created/updated
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        count = SalesRevenueReportAggregator.aggregate_from_import()
        logger.info(f"Sales revenue report aggregation completed: {count} records")
        return {"status": "success", "count": count}
    except Exception as e:
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        logger.error(f"Sales revenue report aggregation failed: {e}")
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True)
def generate_kpi_period_task(self, month_str):
    """Generate KPI assessment period for a specific month asynchronously.

    This task is called from the API to generate KPI periods on-demand.

    Args:
        self: Task instance (bind=True)
        month_str: Month in YYYY-MM format

    Returns:
        dict: Result with period_id and statistics
    """
    from apps.payroll.models import KPIAssessmentPeriod, KPIConfig
    from apps.payroll.utils import (
        generate_department_assessments_for_period,
        generate_employee_assessments_for_period,
    )

    try:
        # Parse month (YYYY-MM format)
        year, month = map(int, month_str.split("-"))
        target_month = date(year, month, 1)

        # Get latest KPIConfig
        kpi_config = KPIConfig.objects.first()
        if not kpi_config:
            return {"error": "No KPI configuration found. Please create one first."}

        # Create assessment period with transaction
        with transaction.atomic():
            period = KPIAssessmentPeriod.objects.create(
                month=target_month,
                kpi_config_snapshot=kpi_config.config,
                finalized=False,
                created_by=None,
            )

            # Update task state for progress tracking
            self.update_state(state="PROGRESS", meta={"status": "Generating employee assessments"})

            # Generate employee assessments for all targets
            employee_count = generate_employee_assessments_for_period(period)

            # Update task state for progress tracking
            self.update_state(state="PROGRESS", meta={"status": "Generating department assessments"})

            # Generate department assessments
            department_count = generate_department_assessments_for_period(period)

        return {
            "period_id": period.id,
            "month": target_month.strftime("%Y-%m"),
            "employee_assessments_created": employee_count,
            "department_assessments_created": department_count,
            "status": "completed",
        }

    except Exception as e:
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        return {"error": str(e)}


@shared_task
def generate_kpi_assessment_period_task():
    """Generate KPI assessment period for the previous month.

    This task is intended to run on the first day of each month to create
    KPI assessment periods for the previous month that just ended.

    Returns:
        dict: Result with status, message, and details
    """
    from apps.payroll.models import KPIAssessmentPeriod, KPIConfig
    from apps.payroll.utils import (
        generate_department_assessments_for_period,
        generate_employee_assessments_for_period,
    )

    # Calculate the previous month
    today = date.today()
    # Get the first day of current month, then subtract one day to get last day of previous month
    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    # Get the first day of previous month
    previous_month = last_day_previous_month.replace(day=1)

    try:
        # Check if period already exists
        if KPIAssessmentPeriod.objects.filter(month=previous_month).exists():
            message = f"KPI assessment period for {previous_month.strftime('%Y-%m')} already exists"
            return {
                "status": "skipped",
                "message": message,
                "month": previous_month.strftime("%Y-%m"),
                "employee_assessments_created": 0,
                "department_assessments_created": 0,
            }

        # Get latest KPIConfig
        kpi_config = KPIConfig.objects.first()
        if not kpi_config:
            message = "No KPI configuration found. Please create one first."
            return {
                "status": "failed",
                "message": message,
                "error": "No KPI configuration available",
            }

        # Create assessment period with transaction
        with transaction.atomic():
            period = KPIAssessmentPeriod.objects.create(
                month=previous_month,
                kpi_config_snapshot=kpi_config.config,
                finalized=False,
                created_by=None,  # System-generated
            )

            # Generate employee assessments for all targets
            employee_count = generate_employee_assessments_for_period(period)

            # Generate department assessments
            department_count = generate_department_assessments_for_period(period)

        message = f"KPI assessment period for {previous_month.strftime('%Y-%m')} generated successfully"
        return {
            "status": "success",
            "message": message,
            "period_id": period.id,
            "month": previous_month.strftime("%Y-%m"),
            "employee_assessments_created": employee_count,
            "department_assessments_created": department_count,
        }

    except Exception as e:
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        error_message = f"Failed to generate KPI assessment period for {previous_month.strftime('%Y-%m')}: {e}"
        return {
            "status": "failed",
            "message": error_message,
            "error": str(e),
        }


@shared_task
def check_kpi_assessment_deadline_and_finalize_task():  # noqa: C901
    """Check if any salary period has KPI assessment deadline yesterday and finalize corresponding KPI periods.

    This task should be scheduled to run daily. It checks if the current or most recent
    salary period has a kpi_assessment_deadline that was yesterday, and if so,
    finalizes the KPI assessment period for the same month.

    Returns:
        dict: Result with status, message, and details
    """
    from apps.payroll.models import DepartmentKPIAssessment, EmployeeKPIAssessment, KPIAssessmentPeriod, SalaryPeriod
    from apps.payroll.utils import update_department_assessment_status

    today = date.today()
    yesterday = today - timedelta(days=1)

    try:
        # Find salary periods where kpi_assessment_deadline was yesterday
        salary_periods_to_check = SalaryPeriod.objects.filter(kpi_assessment_deadline=yesterday)

        if not salary_periods_to_check.exists():
            return {
                "status": "skipped",
                "message": f"No salary periods with KPI assessment deadline on {yesterday.strftime('%Y-%m-%d')}",
                "periods_processed": 0,
            }

        processed_periods = []

        for salary_period in salary_periods_to_check:
            # Find corresponding KPI assessment period for the same month
            try:
                kpi_period = KPIAssessmentPeriod.objects.get(month=salary_period.month)
            except KPIAssessmentPeriod.DoesNotExist:
                processed_periods.append(
                    {
                        "month": salary_period.month.strftime("%Y-%m"),
                        "status": "skipped",
                        "reason": "No KPI assessment period found for this month",
                    }
                )
                continue

            # Check if already finalized
            if kpi_period.finalized:
                processed_periods.append(
                    {
                        "month": salary_period.month.strftime("%Y-%m"),
                        "status": "skipped",
                        "reason": "KPI period already finalized",
                    }
                )
                continue

            # Finalize the KPI period (replicate the logic from the API view)
            with transaction.atomic():
                # Process employee assessments - set default grade for ungraded employees
                employees_set_to_c = 0
                employee_assessments = EmployeeKPIAssessment.objects.filter(period=kpi_period)

                # First pass: set default grades without triggering signals
                employees_to_update = []
                for assessment in employee_assessments:
                    # If not assessed (no scores), set grade_hrm = 'C'
                    if (
                        assessment.total_employee_score is None
                        and assessment.total_manager_score is None
                        and not assessment.grade_hrm
                        and not assessment.grade_manager
                    ):
                        assessment.grade_hrm = "C"
                        employees_set_to_c += 1
                        employees_to_update.append(assessment)

                # Bulk update to avoid triggering signal for each save
                if employees_to_update:
                    EmployeeKPIAssessment.objects.bulk_update(employees_to_update, ["grade_hrm"], batch_size=100)

                # Second pass: finalize all employee assessments
                for assessment in employee_assessments:
                    assessment.finalized = True

                EmployeeKPIAssessment.objects.bulk_update(employee_assessments, ["finalized"], batch_size=100)

                # Process department assessments - update all department statuses
                departments_validated = 0
                departments_invalid = 0
                department_assessments = DepartmentKPIAssessment.objects.filter(period=kpi_period)

                for dept_assessment in department_assessments:
                    # Update department status (is_finished and is_valid_unit_control)
                    update_department_assessment_status(dept_assessment)

                    # Refresh from db to get updated values
                    dept_assessment.refresh_from_db()

                    # Finalize the department assessment
                    dept_assessment.finalized = True
                    dept_assessment.save(update_fields=["finalized"])

                    if dept_assessment.is_valid_unit_control:
                        departments_validated += 1
                    else:
                        departments_invalid += 1

                # Finalize the period
                kpi_period.finalized = True
                kpi_period.updated_by = None  # System-finalized
                kpi_period.save()

            processed_periods.append(
                {
                    "month": salary_period.month.strftime("%Y-%m"),
                    "status": "finalized",
                    "employees_set_to_c": employees_set_to_c,
                    "departments_validated": departments_validated,
                    "departments_invalid": departments_invalid,
                }
            )

        return {
            "status": "success",
            "message": f"Processed {len(processed_periods)} salary periods with KPI deadline on {yesterday.strftime('%Y-%m-%d')}",
            "periods_processed": len(processed_periods),
            "details": processed_periods,
        }

    except Exception as e:
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        error_message = f"Failed to check KPI assessment deadlines for {yesterday.strftime('%Y-%m-%d')}: {e}"
        return {
            "status": "failed",
            "message": error_message,
            "error": str(e),
        }
