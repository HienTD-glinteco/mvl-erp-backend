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


@receiver(pre_save, sender=EmployeeWorkHistory)
def track_work_history_changes(sender, instance, **kwargs):  # noqa: ARG001
    """Track work history changes before save.

    Store the old state in a temporary attribute so we can create a snapshot
    in the post_save signal.
    """
    if instance.pk:
        try:
            old_instance = EmployeeWorkHistory.objects.get(pk=instance.pk)
            instance._old_snapshot = {
                "date": old_instance.date,
                "name": old_instance.name,
                "branch_id": old_instance.branch_id,
                "block_id": old_instance.block_id,
                "department_id": old_instance.department_id,
                "status": old_instance.status,
                "previous_data": old_instance.previous_data,
            }
        except EmployeeWorkHistory.DoesNotExist:
            instance._old_snapshot = None
    else:
        instance._old_snapshot = None


@receiver(post_save, sender=EmployeeWorkHistory)
def trigger_hr_reports_aggregation_on_save(sender, instance, created, **kwargs):  # noqa: ARG001
    """Trigger HR reports aggregation when work history is created or updated.

    This signal fires a Celery task to incrementally update HR reports
    using snapshot data to avoid race conditions.
    """
    from apps.hrm.tasks import aggregate_hr_reports_for_work_history

    # Only trigger if the work history has required organizational fields
    if instance.branch_id and instance.block_id and instance.department_id:
        # Create current snapshot
        current_snapshot = {
            "date": instance.date,
            "name": instance.name,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "status": instance.status,
            "previous_data": instance.previous_data,
        }
        
        if created:
            # Create event: previous is None, current is new state
            snapshot = {"previous": None, "current": current_snapshot}
            aggregate_hr_reports_for_work_history.delay("create", snapshot)
        else:
            # Update event: previous is old state, current is new state
            previous_snapshot = getattr(instance, "_old_snapshot", None)
            snapshot = {"previous": previous_snapshot, "current": current_snapshot}
            aggregate_hr_reports_for_work_history.delay("update", snapshot)


@receiver(post_delete, sender=EmployeeWorkHistory)
def trigger_hr_reports_aggregation_on_delete(sender, instance, **kwargs):  # noqa: ARG001
    """Trigger HR reports aggregation when work history is deleted.

    This signal fires a Celery task to decrementally update HR reports
    using snapshot data.
    """
    from apps.hrm.tasks import aggregate_hr_reports_for_work_history

    # Trigger incremental update for deletion
    if instance.date and instance.branch_id and instance.block_id and instance.department_id:
        # Delete event: previous is deleted state, current is None
        previous_snapshot = {
            "date": instance.date,
            "name": instance.name,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "status": instance.status,
            "previous_data": instance.previous_data,
        }
        snapshot = {"previous": previous_snapshot, "current": None}
        aggregate_hr_reports_for_work_history.delay("delete", snapshot)


# Recruitment Reports Aggregation Signals


@receiver(pre_save, sender=RecruitmentCandidate)
def track_candidate_changes(sender, instance, **kwargs):  # noqa: ARG001
    """Track recruitment candidate changes before save.

    Store the old state in a temporary attribute so we can create a snapshot
    in the post_save signal.
    """
    if instance.pk:
        try:
            old_instance = RecruitmentCandidate.objects.select_related(
                "recruitment_source", "recruitment_channel", "referrer"
            ).get(pk=instance.pk)
            instance._old_snapshot = {
                "status": old_instance.status,
                "onboard_date": old_instance.onboard_date,
                "branch_id": old_instance.branch_id,
                "block_id": old_instance.block_id,
                "department_id": old_instance.department_id,
                "recruitment_source_id": old_instance.recruitment_source_id,
                "recruitment_channel_id": old_instance.recruitment_channel_id,
                "source_allow_referral": old_instance.recruitment_source.allow_referral,
                "channel_belong_to": old_instance.recruitment_channel.belong_to,
                "years_of_experience": old_instance.years_of_experience,
                "referrer_id": old_instance.referrer_id,
            }
        except RecruitmentCandidate.DoesNotExist:
            instance._old_snapshot = None
    else:
        instance._old_snapshot = None


@receiver(post_save, sender=RecruitmentCandidate)
def trigger_recruitment_reports_aggregation_on_save(sender, instance, created, **kwargs):  # noqa: ARG001
    """Trigger recruitment reports aggregation when candidate is created or updated.

    This signal fires a Celery task to incrementally update recruitment reports
    using snapshot data to avoid race conditions.
    """
    from apps.hrm.tasks import aggregate_recruitment_reports_for_candidate

    # Only trigger if the candidate has required organizational fields
    if instance.branch_id and instance.block_id and instance.department_id:
        # Get related data for snapshot
        recruitment_source = instance.recruitment_source
        recruitment_channel = instance.recruitment_channel
        
        # Create current snapshot
        current_snapshot = {
            "status": instance.status,
            "onboard_date": instance.onboard_date,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "recruitment_source_id": instance.recruitment_source_id,
            "recruitment_channel_id": instance.recruitment_channel_id,
            "source_allow_referral": recruitment_source.allow_referral if recruitment_source else False,
            "channel_belong_to": recruitment_channel.belong_to if recruitment_channel else None,
            "years_of_experience": instance.years_of_experience,
            "referrer_id": instance.referrer_id,
        }
        
        if created:
            # Create event: previous is None, current is new state
            snapshot = {"previous": None, "current": current_snapshot}
            aggregate_recruitment_reports_for_candidate.delay("create", snapshot)
        else:
            # Update event: previous is old state, current is new state
            previous_snapshot = getattr(instance, "_old_snapshot", None)
            snapshot = {"previous": previous_snapshot, "current": current_snapshot}
            aggregate_recruitment_reports_for_candidate.delay("update", snapshot)


@receiver(post_delete, sender=RecruitmentCandidate)
def trigger_recruitment_reports_aggregation_on_delete(sender, instance, **kwargs):  # noqa: ARG001
    """Trigger recruitment reports aggregation when candidate is deleted.

    This signal fires a Celery task to decrementally update recruitment reports
    using snapshot data.
    """
    from apps.hrm.tasks import aggregate_recruitment_reports_for_candidate

    # Trigger incremental update for deletion
    if instance.branch_id and instance.block_id and instance.department_id:
        # Get related data for snapshot
        recruitment_source = instance.recruitment_source
        recruitment_channel = instance.recruitment_channel
        
        # Delete event: previous is deleted state, current is None
        previous_snapshot = {
            "status": instance.status,
            "onboard_date": instance.onboard_date,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "recruitment_source_id": instance.recruitment_source_id,
            "recruitment_channel_id": instance.recruitment_channel_id,
            "source_allow_referral": recruitment_source.allow_referral if recruitment_source else False,
            "channel_belong_to": recruitment_channel.belong_to if recruitment_channel else None,
            "years_of_experience": instance.years_of_experience,
            "referrer_id": instance.referrer_id,
        }
        snapshot = {"previous": previous_snapshot, "current": None}
        aggregate_recruitment_reports_for_candidate.delay("delete", snapshot)


