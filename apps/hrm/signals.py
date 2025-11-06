"""Signal handlers for HRM app."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeCertificate,
    EmployeeDependent,
    EmployeeRelationship,
    EmployeeWorkHistory,
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


# HR Reports Aggregation Signals


@receiver(post_save, sender=EmployeeWorkHistory)
def trigger_hr_reports_aggregation_on_save(sender, instance, created, **kwargs):  # noqa: ARG001
    """Trigger HR reports aggregation when work history is created or updated.

    This signal fires a Celery task to incrementally update HR reports
    for the date of the work history event.
    """
    from apps.hrm.tasks import aggregate_hr_reports_for_work_history

    # Only trigger if the work history has required organizational fields
    if instance.branch_id and instance.block_id and instance.department_id:
        event_type = "create" if created else "update"
        aggregate_hr_reports_for_work_history.delay(instance.id, event_type=event_type)


@receiver(post_delete, sender=EmployeeWorkHistory)
def trigger_hr_reports_aggregation_on_delete(sender, instance, **kwargs):  # noqa: ARG001
    """Trigger HR reports aggregation when work history is deleted.

    This signal fires a Celery task to decrementally update HR reports
    for the date of the deleted work history event.
    """
    from apps.hrm.tasks import aggregate_hr_reports_for_work_history

    # Trigger incremental update for deletion
    if instance.date and instance.branch_id and instance.block_id and instance.department_id:
        old_values = {
            "date": instance.date,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "name": instance.name,
            "status": instance.status,
            "previous_data": instance.previous_data,
        }
        aggregate_hr_reports_for_work_history.delay(
            instance.id, event_type="delete", old_values=old_values
        )


# Recruitment Reports Aggregation Signals


@receiver(post_save, sender=RecruitmentCandidate)
def trigger_recruitment_reports_aggregation_on_save(sender, instance, created, **kwargs):  # noqa: ARG001
    """Trigger recruitment reports aggregation when candidate is created or updated.

    This signal fires a Celery task to aggregate recruitment reports,
    especially when a candidate status changes to HIRED.
    """
    from apps.hrm.tasks import aggregate_recruitment_reports_for_candidate  # noqa: PLC0415

    # Only trigger if the candidate has required organizational fields
    if instance.branch_id and instance.block_id and instance.department_id:
        # Trigger aggregation for all status changes, but especially HIRED
        aggregate_recruitment_reports_for_candidate.delay(instance.id)


@receiver(post_delete, sender=RecruitmentCandidate)
def trigger_recruitment_reports_aggregation_on_delete(sender, instance, **kwargs):  # noqa: ARG001
    """Trigger recruitment reports aggregation when candidate is deleted.

    This signal fires a Celery task to re-aggregate recruitment reports for the date
    of the deleted candidate to ensure data consistency.
    """
    from apps.hrm.tasks import aggregate_recruitment_reports_batch  # noqa: PLC0415

    # Trigger batch aggregation for the onboard date if the candidate was hired
    if instance.status == RecruitmentCandidate.Status.HIRED and instance.onboard_date:
        aggregate_recruitment_reports_batch.delay(target_date=instance.onboard_date.isoformat())

