"""Signal handlers for Employee model."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.core.models import Role
from apps.hrm.constants import EmployeeType
from apps.hrm.models import Contract, Employee
from apps.hrm.services.employee import create_employee_type_change_event
from apps.hrm.tasks.timesheets import prepare_monthly_timesheets

User = get_user_model()


@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):  # noqa: ARG001
    """Create a User instance for the Employee after it is created.

    This signal handler automatically creates a User account when an Employee
    is created. It uses the employee's username and email fields.
    """
    # Only create user if employee was just created and doesn't have a user yet
    if created and not instance.user:
        default_role = Role.objects.filter(is_default_role=True).first()
        user = User.objects.create_user(
            username=instance.username,
            email=instance.email,
            first_name=instance.fullname.split()[0] if instance.fullname else "",
            last_name=" ".join(instance.fullname.split()[1:]) if len(instance.fullname.split()) > 1 else "",
            phone_number=instance.phone,
            role=default_role,
        )
        # Update the employee with the created user
        instance.user = user
        instance.save(update_fields=["user"])


@receiver(post_save, sender=Employee)
def prepare_timesheet_on_hire_post_save(sender, instance: Employee, created, **kwargs):
    """Prepare timesheet rows when an employee is created or returns to an active status.

    - If the employee is newly created and has an active status, schedule timesheet preparation for the current month.
    - If the employee's status changes from a leave status (e.g., resigned) to an active status, schedule timesheet preparation.
    """
    working_statuses = Employee.Status.get_working_statuses()
    leave_statuses = Employee.Status.get_leave_statuses()

    # If the employee was just created and is in an active status, schedule timesheet preparation for the current month.
    if created and instance.status in working_statuses:
        prepare_monthly_timesheets.apply_async(employee_id=instance.id, countdown=5)
        return

    # If this is an update and the employee's status changed from a leave status to an active status, schedule timesheet preparation.
    old_status = getattr(instance, "old_status", None)
    if old_status in leave_statuses and instance.status in working_statuses:
        prepare_monthly_timesheets.apply_async(employee_id=instance.id, increment_leave=False, countdown=5)


@receiver(pre_save, sender=Employee)
def track_employee_type_change(sender, instance: Employee, **kwargs):  # noqa: ARG001
    """Track employee_type changes by storing the old value before save.

    This pre_save signal stores the original employee_type value in
    instance._old_employee_type for comparison in the post_save signal.
    """
    if instance.pk:
        try:
            old_instance = Employee.objects.get(pk=instance.pk)
            instance._old_employee_type = old_instance.employee_type  # type: ignore[attr-defined]
        except Employee.DoesNotExist:
            instance._old_employee_type = None  # type: ignore[attr-defined]
    else:
        instance._old_employee_type = None  # type: ignore[attr-defined]


@receiver(post_save, sender=Employee)
def create_employee_type_change_work_history(sender, instance: Employee, created, **kwargs):  # noqa: ARG001
    """Create EmployeeWorkHistory when employee_type changes.

    This post_save signal creates an EmployeeWorkHistory record with
    EventType.CHANGE_EMPLOYEE_TYPE when the employee_type field is modified.

    The context for creating the work history record should be passed via
    instance._change_type_signal_context with the following structure:
    {
        "effective_date": date,           # Required - date when the change takes effect
        "note": str,                       # Optional - additional notes
        "decision": Decision | None,       # Optional - associated decision
        "contract": Contract | None,       # Optional - associated contract (from import)
    }

    If no context is provided but employee_type changed, it will use today's
    date and empty note/decision as defaults.
    """
    if created:
        return

    # Check if _old_employee_type attribute exists (set by pre_save signal)
    if not hasattr(instance, "_old_employee_type"):
        return

    old_employee_type = instance._old_employee_type

    # Skip if no change detected (old and new values are the same)
    if old_employee_type == instance.employee_type:
        return

    # Get context or use defaults
    context = getattr(instance, "_change_type_signal_context", {})
    effective_date = context.get("effective_date", timezone.localdate())
    note = context.get("note", "")
    decision = context.get("decision")
    contract = context.get("contract")

    # Create work history using the service function with all optional params
    create_employee_type_change_event(
        employee=instance,
        old_employee_type=old_employee_type,
        new_employee_type=instance.employee_type,
        effective_date=effective_date,
        note=note,
        decision=decision,
        contract=contract,
        block=instance.block,
        branch=instance.branch,
        department=instance.department,
        position=instance.position,
    )

    # Clean up temporary attributes
    if hasattr(instance, "_old_employee_type"):
        del instance._old_employee_type
    if hasattr(instance, "_change_type_signal_context"):
        del instance._change_type_signal_context


@receiver(post_save, sender=Employee)
def expire_contracts_on_employee_exit(sender, instance: Employee, created, **kwargs):
    """
    Expire all contracts when an employee leaves or becomes unpaid official.

    Update the status of all contracts to `EXPIRED`.
    For the active one only, save the `expiration_date` with `resignation_start_date`.
    """
    if instance.status != Employee.Status.RESIGNED and instance.employee_type != EmployeeType.UNPAID_OFFICIAL:
        return

    base_qs = Contract.objects.filter(employee=instance)
    base_qs.filter(status=Contract.ContractStatus.ACTIVE).update(
        expiration_date=instance.resignation_start_date,
    )
    base_qs.update(status=Contract.ContractStatus.EXPIRED)
