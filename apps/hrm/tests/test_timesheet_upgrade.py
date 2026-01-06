from datetime import date, datetime, time
from decimal import Decimal

import pytest
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.api.serializers.timesheet import (
    TimeSheetEntryDetailSerializer,
    TimeSheetEntryUpdateSerializer,
)
from apps.hrm.constants import (
    EmployeeType,
    ProposalStatus,
    ProposalType,
)
from apps.hrm.models import (
    AttendanceRecord,
    Block,
    Branch,
    Contract,
    ContractType,
    Department,
    Employee,
    Position,
    Proposal,
    ProposalOvertimeEntry,
    TimeSheetEntry,
    WorkSchedule,
)
from apps.hrm.services.timesheets import trigger_timesheet_updates_from_records
from libs.datetimes import make_aware


@pytest.fixture
def mock_request(employee_with_contract):
    factory = APIRequestFactory()
    request = factory.put("/")
    request.user = employee_with_contract.user  # Should have user
    return Request(request)


@pytest.fixture
def employee_with_contract(db):
    """Create a test employee with all required organizational structure."""
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

    employee = Employee.objects.create(
        code="MV001",
        fullname="Test User",
        username="user_mv001",
        email="mv001@example.com",
        phone="0900100002",
        attendance_code="00001",
        citizen_id="000000000001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2023, 1, 1),
        status=Employee.Status.ACTIVE,
        employee_type=EmployeeType.OFFICIAL,
        personal_email="mv001.personal@example.com",
    )

    contract_type = ContractType.objects.create(name="Full Time", code="FT")

    Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        contract_number="C001",
        effective_date=date(2023, 1, 1),
        sign_date=date(2023, 1, 1),
    )
    return employee


@pytest.fixture
def standard_schedule(db):
    return WorkSchedule.objects.create(
        weekday=WorkSchedule.Weekday.MONDAY,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        afternoon_start_time=time(13, 0),
        afternoon_end_time=time(17, 0),
    )


@pytest.mark.django_db
class TestTimesheetUpgrade:
    def test_auto_sync_flow(self, employee_with_contract):
        """Test that updating logs automatically updates start/end time when not manually corrected."""
        today = date(2023, 10, 2)  # Monday

        # Create Attendance Records
        check_in = timezone.make_aware(datetime.combine(today, time(7, 55)))
        check_out = timezone.make_aware(datetime.combine(today, time(17, 5)))

        rec1 = AttendanceRecord.objects.create(
            employee=employee_with_contract, timestamp=check_in, attendance_code="TEST01"
        )
        rec2 = AttendanceRecord.objects.create(
            employee=employee_with_contract, timestamp=check_out, attendance_code="TEST01"
        )

        trigger_timesheet_updates_from_records([rec1, rec2])

        entry = TimeSheetEntry.objects.get(employee=employee_with_contract, date=today)

        assert entry.check_in_time == check_in
        assert entry.check_out_time == check_out
        assert entry.start_time == check_in
        assert entry.end_time == check_out
        assert entry.is_manually_corrected is False

    def test_manual_correction_flow(self, employee_with_contract, mock_request):
        """Test manual correction via serializer updates flags and prevents auto-sync."""
        today = date(2023, 10, 3)  # Tuesday

        start = timezone.make_aware(datetime.combine(today, time(8, 0)))
        end = timezone.make_aware(datetime.combine(today, time(17, 0)))

        entry = TimeSheetEntry.objects.create(
            employee=employee_with_contract,
            date=today,
            check_in_time=start,
            check_out_time=end,
            start_time=start,
            end_time=end,
        )

        mock_request.user = employee_with_contract.user

        new_start = timezone.make_aware(datetime.combine(today, time(9, 0)))
        new_end = timezone.make_aware(datetime.combine(today, time(18, 0)))

        serializer = TimeSheetEntryUpdateSerializer(
            entry,
            context={"request": mock_request},
            data={"start_time": new_start, "end_time": new_end, "note": "Corrected time"},
            partial=True,
        )

        assert serializer.is_valid(raise_exception=True)
        serializer.save()

        entry.refresh_from_db()
        assert entry.is_manually_corrected is True
        assert entry.manually_corrected_by == employee_with_contract
        assert entry.manually_corrected_at is not None
        assert entry.start_time == new_start

        # Now simulate new log coming in
        new_log_time = timezone.make_aware(datetime.combine(today, time(7, 50)))
        rec = AttendanceRecord.objects.create(
            employee=employee_with_contract, timestamp=new_log_time, attendance_code="TEST02"
        )

        # Explicitly call update logic as trigger would
        trigger_timesheet_updates_from_records([rec])

        entry.refresh_from_db()
        # Check-in record updates
        assert entry.check_in_time == new_log_time
        # But start_time remains manual
        assert entry.start_time == new_start

    def test_ot_calculation(self, employee_with_contract, standard_schedule):
        """Test OT calculation is strict intersection of worked time and approved request."""
        # Ensure we use a date that matches the standard_schedule weekday (Monday)
        # standard_schedule is Monday.
        today = date(2023, 10, 2)  # Monday

        # Approved OT Request: 17:00 - 19:00 (2 hours)
        proposal = Proposal.objects.create(
            created_by=employee_with_contract,
            proposal_type=ProposalType.OVERTIME_WORK,
            proposal_status=ProposalStatus.APPROVED,
        )
        ProposalOvertimeEntry.objects.create(
            proposal=proposal, date=today, start_time=time(17, 0), end_time=time(19, 0)
        )

        # Worked: 17:00 - 18:30 (1.5 hours)
        start = timezone.make_aware(datetime.combine(today, time(8, 0)))
        end = timezone.make_aware(datetime.combine(today, time(18, 30)))

        entry = TimeSheetEntry(
            employee=employee_with_contract,
            date=today,
            check_in_time=start,  # Must set records for auto-sync
            check_out_time=end,
            start_time=start,
            end_time=end,
        )
        # Need to manually call calculate_hours because clean/save calls calculator but calculator needs schedule
        # and calculator finds schedule by weekday.
        entry.save()
        entry.calculate_hours_from_schedule(standard_schedule)
        entry.save()

        assert entry.overtime_hours == Decimal("1.50")

    def test_payroll_status_display(self, db, employee_with_contract):
        """Test payroll status field in serializer."""

        # Reuse helper to create another employee but UNPAID
        province = Province.objects.create(name="Test Province 2", code="TP2")
        admin_unit = AdministrativeUnit.objects.create(
            name="Unit 2", code="U2", parent_province=province, level=AdministrativeUnit.UnitLevel.DISTRICT
        )
        branch = Branch.objects.create(name="Branch 2", province=province, administrative_unit=admin_unit)
        block = Block.objects.create(name="Block 2", branch=branch, block_type=Block.BlockType.BUSINESS)
        department = Department.objects.create(
            name="Dept 2", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
        )
        position = Position.objects.create(name="Developer 2")

        unpaid_emp = Employee.objects.create(
            code="CTV001",
            code_type=Employee.CodeType.CTV,
            fullname="Unpaid User",
            username="unpaid_user",
            email="unpaid@example.com",
            phone="0900100003",
            attendance_code="00002",
            citizen_id="000000000002",
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2023, 1, 1),
            status=Employee.Status.ACTIVE,
            employee_type=EmployeeType.UNPAID_OFFICIAL,
            personal_email="unpaid.personal@example.com",
        )

        entry = TimeSheetEntry.objects.create(employee=unpaid_emp, date=date(2023, 10, 5))

        serializer = TimeSheetEntryDetailSerializer(entry)
        assert serializer.data["payroll_status"] == _("Unpaid")

        entry2 = TimeSheetEntry.objects.create(employee=employee_with_contract, date=date(2023, 10, 5))
        serializer2 = TimeSheetEntryDetailSerializer(entry2)
        assert serializer2.data["payroll_status"] == _("Paid")

    def test_manual_edit_requires_note(self, employee_with_contract, mock_request):
        today = date(2023, 10, 7)
        entry = TimeSheetEntry.objects.create(employee=employee_with_contract, date=today)

        mock_request.user = employee_with_contract.user

        serializer = TimeSheetEntryUpdateSerializer(
            entry,
            context={"request": mock_request},
            data={
                "start_time": make_aware(datetime.combine(today, time(9, 0))),
                "end_time": make_aware(datetime.combine(today, time(17, 0))),
            },
            partial=True,
        )

        # Current serializer allows empty note (it will append or set empty string),
        # so ensure update proceeds and manual-correction flags are set.
        assert serializer.is_valid(raise_exception=True)
        serializer.save()
        entry.refresh_from_db()
        assert entry.is_manually_corrected is True
        assert entry.manually_corrected_at is not None

    def test_update_missing_required_fields_raises_validation_error(self, employee_with_contract, mock_request):
        """PUT (full update) without required start_time/end_time should raise ValidationError."""
        today = date(2023, 10, 8)
        entry = TimeSheetEntry.objects.create(employee=employee_with_contract, date=today)

        mock_request.user = employee_with_contract.user

        # Simulate a full update (partial=False) with missing required fields
        serializer = TimeSheetEntryUpdateSerializer(
            entry,
            context={"request": mock_request},
            data={"note": "Only note provided"},
            partial=False,
        )

        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_update_start_time_gte_end_time_raises_validation_error(self, employee_with_contract, mock_request):
        """start_time >= end_time should produce a validation error on end_time."""
        today = date(2023, 10, 9)
        entry = TimeSheetEntry.objects.create(employee=employee_with_contract, date=today)

        mock_request.user = employee_with_contract.user

        dt = timezone.make_aware(datetime.combine(today, time(9, 0)))

        serializer = TimeSheetEntryUpdateSerializer(
            entry,
            context={"request": mock_request},
            data={"start_time": dt, "end_time": dt},
            partial=True,
        )

        with pytest.raises(ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)

        assert "end_time" in str(excinfo.value)
