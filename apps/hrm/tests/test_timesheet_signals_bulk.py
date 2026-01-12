from datetime import date
from unittest.mock import MagicMock

import pytest
from django.db.models.signals import post_save

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import (
    AttendanceExemption,
    Block,
    Branch,
    Contract,
    ContractType,
    Department,
    Employee,
    EmployeeMonthlyTimesheet,
    Position,
    Proposal,
    TimeSheetEntry,
)
from apps.hrm.tasks.timesheet_triggers import (
    process_calendar_change,
    process_contract_change,
    process_exemption_change,
    process_proposal_change,
)


@pytest.fixture
def test_employee(db):
    province = Province.objects.create(name="Test Province", code="TP")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test Unit",
        code="TU",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )
    branch = Branch.objects.create(
        name="Test Branch",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(name="Test Block", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer")

    return Employee.objects.create(
        code="MV001",
        fullname="John Doe",
        username="user_mv001",
        email="mv001@example.com",
        personal_email="mv001.personal@example.com",
        phone="0900100001",
        attendance_code="00001",
        citizen_id="000000000001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )


@pytest.mark.django_db
def test_bulk_update_triggers_post_save(test_employee):
    """Test that process_contract_change manually triggers post_save for TimeSheetEntry."""

    # 1. Create a contract
    contract_type = ContractType.objects.create(name="Full Time", code="FT")
    contract = Contract.objects.create(
        employee=test_employee,
        contract_type=contract_type,
        sign_date=date(2025, 1, 1),
        effective_date=date(2025, 1, 1),
        status=Contract.ContractStatus.ACTIVE,
        annual_leave_days=12,
        base_salary=10000000,
    )

    # 2. Create some timesheet entries
    entry1 = TimeSheetEntry.objects.create(employee=test_employee, date=date(2025, 1, 1))
    entry2 = TimeSheetEntry.objects.create(employee=test_employee, date=date(2025, 1, 2))

    # 3. Setup mock listener
    handler = MagicMock()
    post_save.connect(handler, sender=TimeSheetEntry)

    try:
        # 4. Trigger the bulk update process
        process_contract_change(contract)

        # 5. Verify signal was sent for each updated entry
        # Count should be at least 2 (for entry1 and entry2)
        # Note: process_contract_change might affect other entries if they exist,
        # but here we only created 2.
        assert handler.call_count >= 2

        # Verify the arguments of the signal
        found_entry1 = False
        found_entry2 = False
        for call in handler.call_args_list:
            args, kwargs = call
            instance = kwargs.get("instance")
            if instance and instance.id == entry1.id:
                found_entry1 = True
                assert kwargs.get("created") is False
            if instance and instance.id == entry2.id:
                found_entry2 = True
                assert kwargs.get("created") is False

        assert found_entry1, "Signal not sent for entry1"
        assert found_entry2, "Signal not sent for entry2"

        # 6. Verify EmployeeMonthlyTimesheet was marked for refresh
        # The new signal in monthly_timesheet_triggers.py should have caught the post_save
        from apps.hrm.models import EmployeeMonthlyTimesheet

        # Check Jan 2025 monthly report
        monthly_report = EmployeeMonthlyTimesheet.objects.filter(employee=test_employee, month_key="202501").first()

        assert monthly_report is not None, "Monthly report should have been created if missing"
        assert monthly_report.need_refresh is True, "Monthly report should be marked for refresh"

    finally:
        post_save.disconnect(handler, sender=TimeSheetEntry)


@pytest.mark.django_db
def test_calendar_change_triggers_refresh(test_employee):
    """Test that process_calendar_change (Holiday) triggers refresh."""
    # Setup entries
    date_obj = date(2025, 4, 30)
    TimeSheetEntry.objects.create(employee=test_employee, date=date_obj)

    # Trigger logic (simulate Holiday creation)
    process_calendar_change(date_obj, date_obj)

    # Verify monthly refresh
    report = EmployeeMonthlyTimesheet.objects.filter(employee=test_employee, month_key="202504").first()
    assert report is not None
    assert report.need_refresh is True


@pytest.mark.django_db
def test_exemption_change_triggers_refresh(test_employee):
    """Test that process_exemption_change triggers refresh."""
    # Setup entries
    date_obj = date(2025, 5, 10)
    TimeSheetEntry.objects.create(employee=test_employee, date=date_obj)

    exemption = AttendanceExemption(employee=test_employee, effective_date=date(2025, 5, 1))

    # Trigger logic
    process_exemption_change(exemption)

    # Verify monthly refresh
    report = EmployeeMonthlyTimesheet.objects.filter(employee=test_employee, month_key="202505").first()
    assert report is not None
    assert report.need_refresh is True


@pytest.mark.django_db
def test_proposal_change_triggers_refresh(test_employee):
    """Test that process_proposal_change triggers refresh."""
    # Setup entries
    date_obj = date(2025, 6, 15)
    TimeSheetEntry.objects.create(employee=test_employee, date=date_obj)

    proposal = Proposal(
        created_by=test_employee,
        proposal_type=ProposalType.PAID_LEAVE,
        proposal_status=ProposalStatus.APPROVED,
        paid_leave_start_date=date_obj,
        paid_leave_end_date=date_obj,
    )

    # Trigger logic
    process_proposal_change(proposal)

    # Verify monthly refresh
    report = EmployeeMonthlyTimesheet.objects.filter(employee=test_employee, month_key="202506").first()
    assert report is not None
    assert report.need_refresh is True
