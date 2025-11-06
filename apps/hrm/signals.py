"""Signal handlers for HRM app."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeCertificate,
    EmployeeDependent,
    EmployeeRelationship,
    JobDescription,
    Position,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)
from libs.code_generation import register_auto_code_signal

from .constants import TEMP_CODE_PREFIX

User = get_user_model()

register_auto_code_signal(
    Branch,
    Block,
    Department,
    Employee,
    EmployeeCertificate,
    EmployeeDependent,
    EmployeeRelationship,
    Position,
    RecruitmentChannel,
    RecruitmentSource,
    JobDescription,
    RecruitmentRequest,
    RecruitmentCandidate,
    RecruitmentExpense,
    temp_code_prefix=TEMP_CODE_PREFIX,
)


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
def track_employee_changes(sender, instance, **kwargs):  # noqa: ARG001
    """Track employee changes for work history recording.

    Store the old values in temporary attributes so we can detect changes
    in the post_save signal.
    """
    if instance.pk:
        try:
            old_instance = Employee.objects.get(pk=instance.pk)
            instance._old_position = old_instance.position
            instance._old_department = old_instance.department
            instance._old_status = old_instance.status
        except Employee.DoesNotExist:
            instance._old_position = None
            instance._old_department = None
            instance._old_status = None
    else:
        instance._old_position = None
        instance._old_department = None
        instance._old_status = None


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
    from datetime import date as date_module  # noqa: PLC0415

    from apps.hrm.models import OrganizationChart  # noqa: PLC0415

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


@receiver(post_save, sender=Employee)
def create_employee_work_history_on_changes(sender, instance, created, **kwargs):  # noqa: ARG001
    """Create work history records when employee is created or updated.

    This signal handler creates EmployeeWorkHistory records for:
    - New employee creation (status: ONBOARDING or ACTIVE)
    - Status changes (CHANGE_STATUS event)
    - Position changes (CHANGE_POSITION event)
    - Department changes (TRANSFER event)
    """
    from datetime import date as date_module  # noqa: PLC0415

    from apps.hrm.models import EmployeeWorkHistory  # noqa: PLC0415
    from apps.hrm.utils.functions import create_employee_work_history  # noqa: PLC0415

    # Skip if this is from copy operation (has temp code prefix)
    if instance.code.startswith(TEMP_CODE_PREFIX):
        return

    if created:
        # New employee - create initial work history
        detail = f"Employee created with status: {instance.get_status_display()}"
        create_employee_work_history(
            employee=instance,
            event_type=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            event_date=instance.start_date or date_module.today(),
            detail=detail,
        )
    else:
        # Check for status change
        old_status = getattr(instance, "_old_status", None)
        if old_status and old_status != instance.status:
            old_status_display = dict(Employee.Status.choices).get(old_status, old_status)
            detail = f"Status changed from {old_status_display} to {instance.get_status_display()}"
            event_date = instance.resignation_start_date or instance.start_date or date_module.today()
            create_employee_work_history(
                employee=instance,
                event_type=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                event_date=event_date,
                detail=detail,
            )

        # Check for position change (only for existing employees with actual changes)
        old_position = getattr(instance, "_old_position", None)
        if old_position is not None and old_position != instance.position:
            if old_position and instance.position:
                detail = f"Position changed from {old_position.name} to {instance.position.name}"
            elif instance.position:
                detail = f"Position assigned: {instance.position.name}"
            else:
                detail = "Position removed"

            create_employee_work_history(
                employee=instance,
                event_type=EmployeeWorkHistory.EventType.CHANGE_POSITION,
                event_date=date_module.today(),
                detail=detail,
            )

        # Check for department change (transfer)
        old_department = getattr(instance, "_old_department", None)
        if old_department is not None and old_department != instance.department:
            detail = f"Transferred from {old_department.name} to {instance.department.name}"
            create_employee_work_history(
                employee=instance,
                event_type=EmployeeWorkHistory.EventType.TRANSFER,
                event_date=date_module.today(),
                detail=detail,
            )
