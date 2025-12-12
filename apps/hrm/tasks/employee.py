import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.hrm.api.serializers.employee import EmployeeReactiveActionSerializer
from apps.hrm.models import Employee

logger = logging.getLogger(__name__)


@shared_task()
def reactive_maternity_leave_employees_task() -> None:
    """
    Task to automatically reactivate employees from maternity leave.

    This task finds all employees with MATERNITY_LEAVE status whose
    resignation_end_date has passed (is less than or equal to today),
    and reactivates them to ACTIVE status.

    Seniority is retained (start_date is not changed).
    A CHANGE_STATUS work history event is created for each reactivated employee.
    """
    today = timezone.localdate()
    # Find all employees on maternity leave whose leave period has ended
    employees_to_reactivate = Employee.objects.filter(
        status=Employee.Status.MATERNITY_LEAVE,
        resignation_end_date__lt=today,
    )

    reactivated_count = 0
    errors = []

    for employee in employees_to_reactivate:
        try:
            data = {
                "start_date": today,
                "is_seniority_retained": True,
                "description": _("Reactivated from maternity leave automatically by system task."),
            }
            serializer = EmployeeReactiveActionSerializer(instance=employee, data=data, context={"employee": employee})
            serializer.is_valid(raise_exception=True)
            with transaction.atomic():
                serializer.save()

        except Exception as e:
            error_msg = f"Failed to reactivate employee {employee.id}: {e}"
            errors.append(error_msg)
            logger.exception(error_msg)

    logger.info(
        "Maternity leave reactivation task completed: %d employees reactivated, %d errors",
        reactivated_count,
        len(errors),
    )

    if errors:
        logger.warning("Errors during maternity leave reactivation: %s", errors)
