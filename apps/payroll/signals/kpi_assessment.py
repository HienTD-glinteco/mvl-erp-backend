"""KPI assessment related signals.

This module handles:
- Employee KPI assessment status updates
- Department KPI assessment status sync
- KPI assessment creation for new employees
- Notifications for KPI assessments (ASYNC)

PERFORMANCE NOTE:
Notification sending is now ASYNCHRONOUS via Celery tasks to avoid blocking
the main request thread.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.payroll.models import DepartmentKPIAssessment, EmployeeKPIAssessment
from apps.payroll.utils import (
    update_department_assessment_status,
)


@receiver(post_save, sender=EmployeeKPIAssessment)
def handle_employee_kpi_assessment_post_save(sender, instance, created, **kwargs):  # noqa: C901
    """Handle EmployeeKPIAssessment post-save operations.

    Synchronous operations (fast):
    - Update assessment status
    - Update department assessment status

    Asynchronous operations (via tasks):
    - Send notifications
    - Trigger payroll recalculation
    - Invalidate dashboard cache

    This consolidation keeps fast operations synchronous while offloading
    heavy operations to async tasks for better performance.
    """
    # 1. Update department assessment status (keep synchronous - fast operation)
    if instance.department_snapshot:
        try:
            dept_assessment = DepartmentKPIAssessment.objects.get(
                period=instance.period, department=instance.department_snapshot
            )
            # This updates is_finished, grade_distribution, and is_valid_unit_control in one call
            update_department_assessment_status(dept_assessment)
        except DepartmentKPIAssessment.DoesNotExist:
            pass

    # 2. Update assessment status based on completion state (keep synchronous - fast)
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

    # 3. Send notification on creation (ASYNC)
    if created and instance.employee.user:
        from apps.payroll.tasks import send_kpi_notification_task

        send_kpi_notification_task.delay(str(instance.id), instance.period.month.isoformat())

    # 4. Trigger payroll recalculation (ASYNC)
    from apps.payroll.tasks import recalculate_payroll_slip_task

    recalculate_payroll_slip_task.delay(str(instance.employee_id), instance.period.month.isoformat())

    # 5. Invalidate dashboard cache (ASYNC)
    if instance.manager_id:
        from apps.payroll.tasks import invalidate_dashboard_cache_task

        invalidate_dashboard_cache_task.delay("manager", str(instance.manager_id))


@receiver(post_delete, sender=EmployeeKPIAssessment)
def on_kpi_assessment_deleted(sender, instance, **kwargs):
    """Handle EmployeeKPIAssessment deletion - invalidate cache (ASYNC)."""
    if instance.manager_id:
        from apps.payroll.tasks import invalidate_dashboard_cache_task

        invalidate_dashboard_cache_task.delay("manager", str(instance.manager_id))
