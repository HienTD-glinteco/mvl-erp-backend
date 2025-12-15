"""Signal handlers for Employee model."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hrm.constants import EmployeeType
from apps.hrm.models import Contract, Employee
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
        user = User.objects.create_user(
            username=instance.username,
            email=instance.email,
            first_name=instance.fullname.split()[0] if instance.fullname else "",
            last_name=" ".join(instance.fullname.split()[1:]) if len(instance.fullname.split()) > 1 else "",
            phone_number=instance.phone,
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


@receiver(post_save, sender=Employee)
def expire_contracts_on_employee_exit(sender, instance: Employee, created, **kwargs):
    """Expire all contracts when an employee leaves or becomes unpaid official."""
    if instance.status != Employee.Status.RESIGNED and instance.employee_type != EmployeeType.UNPAID_OFFICIAL:
        return

    Contract.objects.filter(employee=instance).update(status=Contract.ContractStatus.EXPIRED)
