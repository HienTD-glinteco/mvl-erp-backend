"""KPI assessment related signals.

This module handles:
- Employee KPI assessment status updates
- Department KPI assessment status sync
- KPI assessment creation for new employees
- Notifications for KPI assessments
"""

from datetime import date

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext as _

from apps.core.models import UserDevice
from apps.notifications.utils import create_notification
from apps.payroll.models import DepartmentKPIAssessment, EmployeeKPIAssessment, KPIAssessmentPeriod
from apps.payroll.utils import (
    create_assessment_items_from_criteria,
    recalculate_assessment_scores,
    update_department_assessment_status,
)


@receiver(post_save, sender=EmployeeKPIAssessment)
def handle_employee_kpi_assessment_post_save(sender, instance, created, **kwargs):  # noqa: C901
    """Handle all post-save operations for EmployeeKPIAssessment.

    This consolidated signal handles:
    1. Update department assessment status and grade distribution
    2. Update assessment status (new/waiting_manager/completed)
    3. Send notification on creation
    4. Trigger payroll recalculation
    """
    # 1. Update department assessment status and grade distribution
    if instance.department_snapshot:
        try:
            dept_assessment = DepartmentKPIAssessment.objects.get(
                period=instance.period, department=instance.department_snapshot
            )
            update_department_assessment_status(dept_assessment)

            # Update grade distribution when employee grade changes
            if instance.grade_manager or instance.grade_hrm:
                dept_assessment.update_grade_distribution()
        except DepartmentKPIAssessment.DoesNotExist:
            pass

    # 2. Update assessment status based on completion state
    needs_update = False
    new_status = None

    has_manager_assessment = instance.total_manager_score is not None or instance.grade_manager is not None
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

    if needs_update:
        EmployeeKPIAssessment.objects.filter(pk=instance.pk).update(status=new_status)

    # 3. Send notification on creation
    if created:
        recipient = instance.employee.user
        if recipient:
            period_str = instance.period.month.strftime("%m/%Y")

            message = _(
                "KPI Assessment for period %(period)s has been created. Please access KPI Assessment to complete."
            ) % {"period": period_str}

            create_notification(
                actor=instance.created_by if instance.created_by else recipient,
                recipient=recipient,
                verb="created",
                target=instance,
                message=message,
                target_client=UserDevice.Client.MOBILE,
            )

    # 4. Trigger payroll recalculation
    from apps.payroll.tasks import recalculate_payroll_slip_task

    recalculate_payroll_slip_task.delay(str(instance.employee_id), instance.period.month.isoformat())


@receiver(post_save, sender="hrm.Employee")
def create_kpi_assessment_for_new_employee(sender, instance, created, **kwargs):
    """Create KPI assessment for newly created employee if period exists.

    When a new employee is created, check if there's an active KPI assessment period
    for the month of their start_date. If yes, create an assessment for them.
    """
    if not created:
        return

    from apps.hrm.models import Department
    from apps.payroll.models import KPICriterion

    if not instance.start_date:
        return

    start_date = instance.start_date
    if isinstance(start_date, str):
        from datetime import datetime

        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    month_date = date(start_date.year, start_date.month, 1)

    try:
        period = KPIAssessmentPeriod.objects.get(month=month_date)
    except KPIAssessmentPeriod.DoesNotExist:
        return

    if not instance.department:
        return

    if instance.department.function == Department.DepartmentFunction.BUSINESS:
        target = "sales"
    else:
        target = "backoffice"

    criteria = KPICriterion.objects.filter(target=target, active=True).order_by("evaluation_type", "order")

    if not criteria.exists():
        return

    if EmployeeKPIAssessment.objects.filter(employee=instance, period=period).exists():
        return

    assessment = EmployeeKPIAssessment.objects.create(
        employee=instance,
        period=period,
        manager=instance.department.leader if hasattr(instance.department, "leader") else None,
        department_snapshot=instance.department,
    )

    create_assessment_items_from_criteria(assessment, list(criteria))
    recalculate_assessment_scores(assessment)
