from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import ProposalType
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

User = get_user_model()


@pytest.fixture
def test_setup_models(db):
    user = User.objects.create_user(username="test_user", email="test@example.com", password="password")

    province = Province.objects.create(name="Test Province", code="TP")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test Admin Unit", code="TAU", parent_province=province, level=AdministrativeUnit.UnitLevel.DISTRICT
    )

    branch = Branch.objects.create(name="Test Branch", code="TB01", province=province, administrative_unit=admin_unit)
    block = Block.objects.create(name="Test Block", code="TBK01", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(name="Test Dept", code="TD01", branch=branch, block=block)
    position = Position.objects.create(name="Test Pos", code="TP01")

    return {"user": user, "branch": branch, "block": block, "department": department, "position": position}


@pytest.mark.django_db
class TestProcessContractChange:
    def test_backfill_logic_active_contract(self, test_setup_models):
        # 1. Create Employee
        employee = Employee.objects.create(
            user=test_setup_models["user"],
            code="EMP001",
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            department=test_setup_models["department"],
            block=test_setup_models["block"],
            branch=test_setup_models["branch"],
            position=test_setup_models["position"],
            attendance_code="AC001",
            start_date=date(2023, 1, 1),
            citizen_id="123456789",
            phone="0123456789",
        )

        # 2. Setup dates
        today = date.today()
        # Ensure we are not on Jan 1st to have some history
        target_year = today.year - 1
        start_date = date(target_year, 1, 1)  # Jan 1st prev year

        # 3. Create Contract effective from Jan 1st
        contract_type = ContractType.objects.create(
            name="Test Type",
            code="TT",
            symbol="TT",  # Add symbol as it might be required
            annual_leave_days=12,
            duration_type=ContractType.DurationType.FIXED,
            duration_months=12,
            base_salary=10000000,
        )

        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            effective_date=start_date,
            sign_date=start_date,
            status=Contract.ContractStatus.ACTIVE,
            base_salary=10000000,
            annual_leave_days=12,
        )

        # 4. Create an existing timesheet entry sometime in March
        existing_entry_date = date(target_year, 3, 15)
        TimeSheetEntry.objects.create(employee=employee, date=existing_entry_date)

        # 5. Run the task
        # We process the contract change.
        # This should backfill Jan, Feb, and part of March (up to 15th).
        process_contract_change(contract)

        # 6. Assertions

        # Check that entries were created for Jan and Feb
        # Verify Jan entry exists (checking first day of Jan)
        jan_entry = TimeSheetEntry.objects.filter(employee=employee, date=date(target_year, 1, 1))
        assert jan_entry.exists(), "Jan 1st entry should exist"

        # Verify Feb entry exists
        feb_entry = TimeSheetEntry.objects.filter(employee=employee, date=date(target_year, 2, 1))
        assert feb_entry.exists(), "Feb 1st entry should exist"

        # Verify Monthly Timesheets
        jan_mts = EmployeeMonthlyTimesheet.objects.filter(employee=employee, month_key=f"{target_year}01").first()
        assert jan_mts is not None, "January Monthly Timesheet should be created"

        feb_mts = EmployeeMonthlyTimesheet.objects.filter(employee=employee, month_key=f"{target_year}02").first()
        assert feb_mts is not None, "February Monthly Timesheet should be created"

        # Verify March MTS exists (created because we span into March)
        mar_mts = EmployeeMonthlyTimesheet.objects.filter(employee=employee, month_key=f"{target_year}03").first()
        assert mar_mts is not None, "March Monthly Timesheet should be created"

    def test_mark_future_months_refresh(self, test_setup_models):
        today = date.today()
        target_year = today.year - 1
        effective_date = date(target_year, 1, 1)

        # Create second user to avoid unique constraint issues
        user2 = User.objects.create_user(username="test_user_2", email="test2@example.com", password="password")

        employee = Employee.objects.create(
            user=user2,
            code="EMP002",
            fullname="Test Employee 2",
            username="testemployee2",
            email="test2@example.com",
            department=test_setup_models["department"],
            block=test_setup_models["block"],
            branch=test_setup_models["branch"],
            position=test_setup_models["position"],
            attendance_code="AC002",
            start_date=effective_date,
            citizen_id="987654321",
            phone="0987654321",
        )

        contract_type = ContractType.objects.create(
            name="Test Type 2",
            code="TT2",
            symbol="TT2",
            annual_leave_days=12,
            duration_type=ContractType.DurationType.FIXED,
            duration_months=12,
            base_salary=10000000,
        )

        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            effective_date=effective_date,
            sign_date=effective_date,
            status=Contract.ContractStatus.ACTIVE,
            base_salary=10000000,
        )

        # Existing entry in March stopping the backfill
        TimeSheetEntry.objects.create(employee=employee, date=date(target_year, 3, 10))

        # Existing calculated MTS for April (simulating old data from future relative to backfill)
        april_mts = EmployeeMonthlyTimesheet.objects.create(
            employee=employee, report_date=date(target_year, 4, 1), month_key=f"{target_year}04", need_refresh=False
        )

        process_contract_change(contract)

        april_mts.refresh_from_db()
        assert april_mts.need_refresh is True, "April MTS should be marked for refresh"


@pytest.mark.django_db
class TestOtherTriggers:
    def test_process_calendar_change(self, test_setup_models):
        user3 = User.objects.create_user(username="test_user_3", email="test3@example.com", password="password")
        employee = Employee.objects.create(
            user=user3,
            code="EMP003",
            fullname="Test Employee 3",
            department=test_setup_models["department"],
            block=test_setup_models["block"],
            branch=test_setup_models["branch"],
            position=test_setup_models["position"],
            attendance_code="AC003",
            start_date=date(2023, 1, 1),
            citizen_id="111222333",
            phone="111222333",
        )

        target_date = date(2023, 1, 10)
        entry = TimeSheetEntry.objects.create(employee=employee, date=target_date)

        with patch("apps.hrm.tasks.timesheet_triggers.TimesheetCalculator") as mock_calc:
            # Make sure compute_all handles boolean arg correctly or mock it properly
            mock_instance = mock_calc.return_value

            process_calendar_change(target_date, target_date)
            mock_calc.assert_called_with(entry)
            mock_instance.compute_all.assert_called()

    def test_process_exemption_change(self, test_setup_models):
        user4 = User.objects.create_user(username="test_user_4", email="test4@example.com", password="password")
        employee = Employee.objects.create(
            user=user4,
            code="EMP004",
            fullname="Test Employee 4",
            department=test_setup_models["department"],
            block=test_setup_models["block"],
            branch=test_setup_models["branch"],
            position=test_setup_models["position"],
            attendance_code="AC004",
            start_date=date(2023, 1, 1),
            citizen_id="444555666",
            phone="444555666",
        )
        effective_date = date(2023, 2, 1)

        exemption = AttendanceExemption.objects.create(
            employee=employee,
            effective_date=effective_date,
            notes="Test Exemption",
            status=AttendanceExemption.Status.ENABLED,
        )

        entry = TimeSheetEntry.objects.create(employee=employee, date=effective_date)

        with patch("apps.hrm.tasks.timesheet_triggers.TimesheetCalculator") as mock_calc:
            process_exemption_change(exemption)
            mock_calc.assert_called_with(entry)
            mock_calc.return_value.compute_all.assert_called()

    def test_process_proposal_change(self, test_setup_models):
        user5 = User.objects.create_user(username="test_user_5", email="test5@example.com", password="password")
        employee = Employee.objects.create(
            user=user5,
            code="EMP005",
            fullname="Test Employee 5",
            department=test_setup_models["department"],
            block=test_setup_models["block"],
            branch=test_setup_models["branch"],
            position=test_setup_models["position"],
            attendance_code="AC005",
            start_date=date(2023, 1, 1),
            citizen_id="777888999",
            phone="777888999",
        )
        start_date = date(2023, 3, 1)
        end_date = date(2023, 3, 2)

        proposal = Proposal.objects.create(
            code="TEST_PROP_001",
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            paid_leave_start_date=start_date,
            paid_leave_end_date=end_date,
            paid_leave_reason="Test Leave",
        )

        entry1 = TimeSheetEntry.objects.create(employee=employee, date=start_date)
        entry2 = TimeSheetEntry.objects.create(employee=employee, date=end_date)

        with patch("apps.hrm.tasks.timesheet_triggers.TimesheetCalculator") as mock_calc:
            process_proposal_change(proposal)
            # Should be called for both entries
            assert mock_calc.call_count == 2
