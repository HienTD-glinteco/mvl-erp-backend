from typing import List, Type

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from apps.hrm.models.contract import Contract
from apps.hrm.models.holiday import Holiday, CompensatoryWorkday
from apps.hrm.models.proposal import Proposal, ProposalStatus
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.models.work_schedule import WorkSchedule
from apps.hrm.models.attendance_exemption import AttendanceExemption
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService


@receiver(post_save, sender=Contract)
def handle_contract_change(sender: Type[Contract], instance: Contract, created: bool, **kwargs):
    """
    When a contract is created or updated:
    1. Find affected TimeSheetEntries (employee matches, date within contract range).
    2. Trigger SnapshotService to update contract info.
    3. Recalculate timesheets.
    """
    if not instance.employee_id:
        return

    # Defer to transaction commit to ensure data consistency
    transaction.on_commit(lambda: _process_contract_change(instance.id))


def _process_contract_change(contract_id: int):
    try:
        contract = Contract.objects.get(id=contract_id)
    except Contract.DoesNotExist:
        return

    # Find affected entries
    # Range: effective_date -> expiration_date (or today/future if null)
    query = TimeSheetEntry.objects.filter(employee_id=contract.employee_id, date__gte=contract.effective_date)
    if contract.expiration_date:
        query = query.filter(date__lte=contract.expiration_date)

    service = TimesheetSnapshotService()

    for entry in query:
        service.snapshot_data(entry) # Update contract/wage_rate/is_full_salary
        entry.save() # Save snapshot data

        # Recalculate metrics (in case is_full_salary affects something, though mostly for payroll)
        # But wait, logic separation: Calculator uses Snapshot fields.
        calc = TimesheetCalculator(entry)
        calc.compute_all()
        entry.save()


@receiver(post_save, sender=Holiday)
@receiver(post_save, sender=CompensatoryWorkday)
def handle_calendar_change(sender, instance, **kwargs):
    """
    When Holiday or CompensatoryWorkday changes:
    1. Find affected TimeSheetEntries (matching date).
    2. Trigger SnapshotService (update day_type).
    3. Recalculate.
    """
    start_date = None
    end_date = None

    if sender == Holiday:
        start_date = instance.start_date
        end_date = instance.end_date
    elif sender == CompensatoryWorkday:
        start_date = instance.date
        end_date = instance.date

    if start_date and end_date:
        transaction.on_commit(lambda: _process_calendar_change(start_date, end_date))


def _process_calendar_change(start_date, end_date):
    entries = TimeSheetEntry.objects.filter(date__range=(start_date, end_date))
    service = TimesheetSnapshotService()

    for entry in entries:
        service.snapshot_data(entry) # Update day_type
        entry.save()

        calc = TimesheetCalculator(entry)
        calc.compute_all()
        entry.save()


@receiver(post_save, sender=AttendanceExemption)
def handle_exemption_change(sender, instance: AttendanceExemption, **kwargs):
    """
    When AttendanceExemption changes:
    1. Update is_exempt on affected entries.
    2. Recalculate (if exempt, recalculation sets full status).
    """
    employee_id = instance.employee_id
    effective_date = instance.effective_date
    transaction.on_commit(lambda: _process_exemption_change(employee_id, effective_date))


def _process_exemption_change(employee_id, effective_date):
    query = TimeSheetEntry.objects.filter(employee_id=employee_id)
    if effective_date:
        query = query.filter(date__gte=effective_date)

    service = TimesheetSnapshotService()
    for entry in query:
        service.snapshot_data(entry) # Update is_exempt
        entry.save()

        calc = TimesheetCalculator(entry)
        calc.compute_all()
        entry.save()


@receiver(post_save, sender=Proposal)
def handle_proposal_change(sender, instance: Proposal, **kwargs):
    """
    When Proposal is APPROVED or REVOKED (changed):
    1. Recalculate affected entries.
    """
    # Only care if status is APPROVED or was APPROVED (if we track old status).
    # Simplification: If proposal touches dates, recalculate those dates for the employee.

    if not instance.created_by_id:
        return

    transaction.on_commit(lambda: _process_proposal_change(instance.id))

def _process_proposal_change(proposal_id):
    try:
        proposal = Proposal.objects.get(id=proposal_id)
    except Proposal.DoesNotExist:
        return

    # Determine date range
    dates = []
    # Collect all possible date fields
    fields = [
        ('paid_leave_start_date', 'paid_leave_end_date'),
        ('unpaid_leave_start_date', 'unpaid_leave_end_date'),
        ('maternity_leave_start_date', 'maternity_leave_end_date'),
        ('late_exemption_start_date', 'late_exemption_end_date'),
        ('post_maternity_benefits_start_date', 'post_maternity_benefits_end_date'),
    ]

    start = None
    end = None

    for s_field, e_field in fields:
        s = getattr(proposal, s_field, None)
        e = getattr(proposal, e_field, None)
        if s:
            start = min(start, s) if start else s
        if e:
            end = max(end, e) if end else e

    if not start:
        return
    if not end:
        end = start

    entries = TimeSheetEntry.objects.filter(
        employee_id=proposal.created_by_id,
        date__range=(start, end)
    )

    for entry in entries:
        # Note: Proposal changes might affect 'is_exempt' ONLY IF we supported Proposal-based exemption in Snapshot.
        # But currently SnapshotService only uses AttendanceExemption model for is_exempt.
        # However, LATE_EXEMPTION proposal affects Grace Period in Calculator.
        # So Recalculate is sufficient.

        calc = TimesheetCalculator(entry)
        calc.compute_all()
        entry.save()
