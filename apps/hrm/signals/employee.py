"""Signal handlers for Employee model."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.hrm.models import Employee
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


@receiver(pre_save, sender=Employee)
def prepare_timesheet_on_hire_pre_save(sender, instance: Employee, **kwargs):
    instance.old_status = None
    if instance.pk:
        try:
            previous = Employee.objects.get(pk=instance.pk)
            instance.old_status = previous.status
        except Employee.DoesNotExist:
            instance.old_status = None


@receiver(post_save, sender=Employee)
def prepare_timesheet_on_hire_post_save(sender, instance: Employee, created, **kwargs):
    """When an employee is created or an employee returns to active status, prepare timesheet rows."""
    # If created and in Active, Onboarding
    if created and instance.status in [Employee.Status.ACTIVE, Employee.Status.ONBOARDING]:
        # Schedule task to prepare current month for the employee
        prepare_monthly_timesheets.delay(employee_id=instance.id)
        return

    # If this is an update and employee has transitioned from RESIGNED to a working status, prepare timesheet
    old_status = getattr(instance, "old_status", None)
    if old_status == Employee.Status.RESIGNED and instance.status != Employee.Status.RESIGNED:
        prepare_monthly_timesheets.delay(employee_id=instance.id)
