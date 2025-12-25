"""Signals for payroll app."""

from datetime import date

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext as _

from apps.core.models import UserDevice
from apps.notifications.utils import create_notification
from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    PenaltyTicket,
    RecoveryVoucher,
    SalesRevenue,
)
from apps.payroll.utils import (
    create_assessment_items_from_criteria,
    recalculate_assessment_scores,
    update_department_assessment_status,
)
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


@receiver(post_save, sender=EmployeeKPIAssessment)
def update_assessment_status(sender, instance, **kwargs):
    """Update assessment status based on completion state.

    Status logic:
    - new: Default when created
    - waiting_manager: Employee has completed self-assessment but manager hasn't assessed
    - completed: Manager has completed assessment
    """
    needs_update = False
    new_status = None

    # Check if manager has assessed (total_manager_score is set or grade_manager exists)
    has_manager_assessment = instance.total_manager_score is not None or instance.grade_manager is not None

    # Check if employee has completed self-assessment (total_employee_score is set)
    has_employee_assessment = instance.total_employee_score is not None

    if has_manager_assessment:
        if instance.status != EmployeeKPIAssessment.StatusChoices.COMPLETED:
            new_status = EmployeeKPIAssessment.StatusChoices.COMPLETED
            needs_update = True
    elif has_employee_assessment:
        if instance.status != EmployeeKPIAssessment.StatusChoices.WAITING_MANAGER:
            new_status = EmployeeKPIAssessment.StatusChoices.WAITING_MANAGER
            needs_update = True
    else:
        if instance.status != EmployeeKPIAssessment.StatusChoices.NEW:
            new_status = EmployeeKPIAssessment.StatusChoices.NEW
            needs_update = True

    # Update status if needed (avoid recursive signal)
    if needs_update:
        EmployeeKPIAssessment.objects.filter(pk=instance.pk).update(status=new_status)


@receiver(post_save, sender=EmployeeKPIAssessment)
def notify_employee_kpi_assessment_created(sender, instance, created, **kwargs):
    """Notify employee when a KPI assessment is created."""
    # Scenario C: KPI Evaluation Created
    if created:
        recipient = instance.employee.user
        if not recipient:
            return

        # Format: MM/YYYY
        period_str = instance.period.month.strftime("%m/%Y")

        message = _(
            "KPI Assessment for period %(period)s has been created. Please access KPI Assessment to complete."
        ) % {"period": period_str}

        create_notification(
            actor=instance.created_by
            if instance.created_by
            else recipient,  # Ideally created_by, but fallback to recipient
            recipient=recipient,
            verb="created",
            target=instance,
            message=message,
            target_client=UserDevice.Client.MOBILE,
        )


"""Signal handlers for Payroll app."""


@receiver(post_save, sender="hrm.Employee")
def create_kpi_assessment_for_new_employee(sender, instance, created, **kwargs):
    """Create KPI assessment for newly created employee if period exists.

    When a new employee is created, check if there's an active KPI assessment period
    for the month of their start_date. If yes, create an assessment for them.
    """
    if not created:
        return

    # Import here to avoid circular import
    from apps.hrm.models import Department
    from apps.payroll.models import KPICriterion

    # Check if employee has start_date
    if not instance.start_date:
        return

    # Get the first day of the month from start_date
    # Note: Django's post_save signal can fire with unconverted field values
    # when objects are created with string dates (e.g., Employee.objects.create(start_date="2023-01-01"))
    # The database will have the correct date, but in-memory instance.start_date might still be a string
    start_date = instance.start_date
    if isinstance(start_date, str):
        from datetime import datetime

        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    month_date = date(start_date.year, start_date.month, 1)

    # Check if KPI assessment period exists for this month
    try:
        period = KPIAssessmentPeriod.objects.get(month=month_date)
    except KPIAssessmentPeriod.DoesNotExist:
        # No period exists for this month
        return

    # Check if employee has department
    if not instance.department:
        return

    # Determine target based on department function
    if instance.department.function == Department.DepartmentFunction.BUSINESS:
        target = "sales"
    else:
        target = "backoffice"

    # Get active criteria for target
    criteria = KPICriterion.objects.filter(target=target, active=True).order_by("evaluation_type", "order")

    if not criteria.exists():
        return

    # Check if assessment already exists
    if EmployeeKPIAssessment.objects.filter(employee=instance, period=period).exists():
        return

    # Create assessment
    assessment = EmployeeKPIAssessment.objects.create(
        employee=instance,
        period=period,
        manager=instance.department.leader if hasattr(instance.department, "leader") else None,
    )

    # Create items from criteria
    create_assessment_items_from_criteria(assessment, list(criteria))

    # Calculate totals
    recalculate_assessment_scores(assessment)


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
    instance.code = f"{SalesRevenue.CODE_PREFIX}-{month_key}-{seq:04d}"
    instance.save(update_fields=["code"])


register_auto_code_signal(
    SalesRevenue,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_sales_revenue_code,
)


def generate_recovery_voucher_code(instance: RecoveryVoucher) -> None:
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
    instance.code = f"{prefix}{str(next_seq).zfill(4)}"
    instance.save(update_fields=["code"])


register_auto_code_signal(
    RecoveryVoucher,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_recovery_voucher_code,
)


def generate_penalty_ticket_code(instance: "PenaltyTicket") -> None:
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

    instance.code = f"{PenaltyTicket.CODE_PREFIX}-{month_str}-{seq}"
    instance.save(update_fields=["code"])


register_auto_code_signal(
    PenaltyTicket,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_penalty_ticket_code,
)


@receiver(post_save, sender=PenaltyTicket)
def on_penalty_ticket_status_changed(sender, instance, created, update_fields, **kwargs):
    """Recalculate payroll when penalty ticket status changes.

    This signal triggers when a PenaltyTicket is saved.
    Recalculates payroll to update penalty blocking status.
    """
    # Skip recalculation on creation or if status wasn't updated
    if created or (update_fields and "status" not in update_fields):
        return

    from apps.payroll.models import PayrollSlip, SalaryPeriod
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

    # Find salary period for this month
    try:
        salary_period = SalaryPeriod.objects.get(month=instance.month)
    except SalaryPeriod.DoesNotExist:
        # No salary period for this month yet
        return

    # Find payroll slip for this employee
    try:
        payroll_slip = PayrollSlip.objects.get(salary_period=salary_period, employee=instance.employee)
    except PayrollSlip.DoesNotExist:
        # No payroll slip yet
        return

    # Recalculate payroll
    calculator = PayrollCalculationService(payroll_slip)
    calculator.calculate()
