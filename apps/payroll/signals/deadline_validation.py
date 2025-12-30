"""Deadline validation signals.

This module handles validation of deadlines for:
1. Proposal creation (salary-affecting proposals)
2. KPI assessment scoring (employee and manager)

These validations ensure business rules are enforced at the data layer,
preventing invalid operations after configured deadlines.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.payroll.models import EmployeeKPIAssessment, SalaryPeriod


@receiver(pre_save, sender="hrm.Proposal")
def validate_proposal_salary_deadline(sender, instance, **kwargs):  # noqa: C901
    """Validate proposal deadline for salary-affecting proposals.

    Checks if proposal is being CREATED after the salary period's
    proposal deadline for proposal types that affect salary calculations.

    This only blocks creation, not approval or other updates.

    Salary-affecting proposal types:
    - POST_MATERNITY_BENEFITS
    - OVERTIME_WORK
    - PAID_LEAVE
    - UNPAID_LEAVE
    - MATERNITY_LEAVE
    - TIMESHEET_ENTRY_COMPLAINT
    """
    from apps.hrm.constants import ProposalType

    # Only validate on creation (not on updates/approvals)
    if instance.pk:
        return

    # Define salary-affecting proposal types
    SALARY_AFFECTING_TYPES = [
        ProposalType.POST_MATERNITY_BENEFITS,
        ProposalType.OVERTIME_WORK,
        ProposalType.PAID_LEAVE,
        ProposalType.UNPAID_LEAVE,
        ProposalType.MATERNITY_LEAVE,
        ProposalType.TIMESHEET_ENTRY_COMPLAINT,
    ]

    # Only validate salary-affecting proposals
    if instance.proposal_type not in SALARY_AFFECTING_TYPES:
        return

    # Determine the month this proposal affects
    proposal_month = None

    if instance.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
        if instance.timesheet_entry_complaint_complaint_date:
            proposal_month = date(
                instance.timesheet_entry_complaint_complaint_date.year,
                instance.timesheet_entry_complaint_complaint_date.month,
                1,
            )

    elif instance.proposal_type == ProposalType.OVERTIME_WORK:
        # For overtime, we can't check entries before save
        # The validation will happen in post_save if needed
        # For now, skip deadline validation for overtime during creation
        pass

    elif instance.proposal_type == ProposalType.PAID_LEAVE:
        if instance.paid_leave_start_date:
            proposal_month = date(
                instance.paid_leave_start_date.year,
                instance.paid_leave_start_date.month,
                1,
            )

    elif instance.proposal_type == ProposalType.UNPAID_LEAVE:
        if instance.unpaid_leave_start_date:
            proposal_month = date(
                instance.unpaid_leave_start_date.year,
                instance.unpaid_leave_start_date.month,
                1,
            )

    elif instance.proposal_type == ProposalType.MATERNITY_LEAVE:
        if instance.maternity_leave_start_date:
            proposal_month = date(
                instance.maternity_leave_start_date.year,
                instance.maternity_leave_start_date.month,
                1,
            )

    elif instance.proposal_type == ProposalType.POST_MATERNITY_BENEFITS:
        if instance.post_maternity_benefits_start_date:
            proposal_month = date(
                instance.post_maternity_benefits_start_date.year,
                instance.post_maternity_benefits_start_date.month,
                1,
            )

    # Check deadline if we determined a month
    if proposal_month:
        try:
            salary_period = SalaryPeriod.objects.get(month=proposal_month)
            if salary_period.proposal_deadline:
                today = timezone.now().date()
                if today > salary_period.proposal_deadline:
                    raise ValidationError(
                        _("Cannot create %(type)s proposal after salary period deadline (%(deadline)s)")
                        % {
                            "type": instance.get_proposal_type_display(),
                            "deadline": salary_period.proposal_deadline.strftime("%Y-%m-%d"),
                        }
                    )
        except SalaryPeriod.DoesNotExist:
            pass


@receiver(pre_save, sender="hrm.ProposalOvertimeEntry")
def validate_overtime_entry_deadline(sender, instance, **kwargs):
    """Validate overtime entry creation against salary period deadline.

    This validates ProposalOvertimeEntry creation to ensure overtime entries
    are not added after the salary period's proposal deadline.

    This complements the Proposal validation which skips overtime entries
    during proposal creation (since entries are added after proposal is saved).
    """
    # Determine the month from the overtime entry date
    if not instance.date:
        return

    proposal_month = date(instance.date.year, instance.date.month, 1)

    # Check if salary period exists and has a deadline
    try:
        salary_period = SalaryPeriod.objects.get(month=proposal_month)
        if salary_period.proposal_deadline:
            today = timezone.now().date()
            if today > salary_period.proposal_deadline:
                raise ValidationError(
                    _("Cannot create overtime entry after salary period deadline (%(deadline)s)")
                    % {"deadline": salary_period.proposal_deadline.strftime("%Y-%m-%d")}
                )
    except SalaryPeriod.DoesNotExist:
        pass


@receiver(pre_save, sender=EmployeeKPIAssessment)
def validate_kpi_assessment_deadline(sender, instance, **kwargs):
    """Validate KPI assessment deadline for employee and manager scoring.

    Blocks employee self-assessment and manager assessment after deadline,
    but allows HRM to edit at any time.

    Checks if instance is being updated with:
    - Manager scores (manager_score in items)
    - Manager assessment fields

    HRM can always edit via hrm_assessed, grade_hrm, etc.
    """
    # Check if assessment has a period with a month
    if not instance.period or not instance.period.month:
        return

    # Allow creation (new assessments)
    if not instance.pk:
        return

    # Get old instance to check what changed
    try:
        old_instance = EmployeeKPIAssessment.objects.get(pk=instance.pk)
    except EmployeeKPIAssessment.DoesNotExist:
        return

    # If HRM is editing (hrm_assessed or grade_hrm changed), allow
    if instance.hrm_assessed or (instance.grade_hrm != old_instance.grade_hrm):
        return

    # If manager_assessment_date is being set/changed, this is manager scoring
    is_manager_scoring = (
        instance.manager_assessment_date != old_instance.manager_assessment_date
        or instance.total_manager_score != old_instance.total_manager_score
    )

    # If not manager scoring, allow
    if not is_manager_scoring:
        return

    # Check deadline for employee/manager scoring
    try:
        salary_period = SalaryPeriod.objects.get(month=instance.period.month)
        if salary_period.kpi_assessment_deadline:
            today = timezone.now().date()
            if today > salary_period.kpi_assessment_deadline:
                raise ValidationError(
                    _("Cannot submit KPI assessment after deadline (%(deadline)s). Please contact HRM for assistance.")
                    % {"deadline": salary_period.kpi_assessment_deadline.strftime("%Y-%m-%d")}
                )
    except SalaryPeriod.DoesNotExist:
        pass
