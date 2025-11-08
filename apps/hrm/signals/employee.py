"""Signal handlers for Employee model."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.hrm.models import Employee

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
def track_position_change(sender, instance, **kwargs):  # noqa: ARG001
    """Track if employee position is changing.

    Store the old position in a temporary attribute so we can detect changes
    in the post_save signal.
    """
    if instance.pk:
        try:
            old_instance = Employee.objects.get(pk=instance.pk)
            instance._old_position = old_instance.position
        except Employee.DoesNotExist:
            instance._old_position = None
    else:
        instance._old_position = None


@receiver(post_save, sender=Employee)
def manage_organization_chart_on_position_change(sender, instance, created, **kwargs):  # noqa: ARG001
    """Manage OrganizationChart entries when employee position changes.

    This signal handler:
    - Deactivates all existing organization chart entries for the employee
    - Creates a new active and primary entry if position is set

    Runs when:
    - Employee is newly created with a position
    - Employee position is changed
    """
    from datetime import date as date_module

    from apps.hrm.models import OrganizationChart

    # Skip if employee doesn't have required fields
    if not instance.position or not instance.department or not instance.user:
        return

    # Determine if we should create OrganizationChart
    if created:
        # New employee with position
        should_create = True
    else:
        # Check if position changed (using tracked old position from pre_save)
        old_position = getattr(instance, "_old_position", None)
        should_create = old_position != instance.position

    if should_create:
        # Deactivate all existing organization chart entries for this employee
        OrganizationChart.objects.filter(employee=instance.user, is_active=True).update(
            is_active=False, is_primary=False
        )

        # Create new organization chart entry
        OrganizationChart.objects.create(
            employee=instance.user,
            position=instance.position,
            department=instance.department,
            block=instance.block,
            branch=instance.branch,
            start_date=instance.start_date or date_module.today(),
            is_primary=True,
            is_active=True,
        )
