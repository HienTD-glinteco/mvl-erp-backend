from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import EmployeeType
from apps.hrm.models import (
    Block,
    Branch,
    Contract,
    ContractType,
    Department,
    Employee,
    TimeSheetEntry,
    WorkSchedule,
)

pytestmark = pytest.mark.django_db


class TestTimesheetContractIntegration:
    """Test integration between Timesheet and Contract models for Phase 2."""

    @pytest.fixture
    def base_data(self):
        """Create base data for testing (branch, block, department)."""
        province = Province.objects.create(code="01", name="Test Province")
        admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=branch,
            block_type=Block.BlockType.BUSINESS,
        )
        department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=branch,
            block=block,
        )
        return {
            "branch": branch,
            "block": block,
            "department": department,
        }

    @pytest.fixture
    def employee(self, base_data):
        """Create test employee."""
        return Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=base_data["branch"],
            block=base_data["block"],
            department=base_data["department"],
            citizen_id="123456789",
        )

    @pytest.fixture
    def contract_type_probation(self):
        """Create a probation contract type with 85% net percentage."""
        return ContractType.objects.create(
            name="Probation Contract",
            symbol="HDTV",
            category=ContractType.Category.CONTRACT,
            duration_type=ContractType.DurationType.FIXED,
            duration_months=2,
            base_salary=Decimal("10000000"),
            net_percentage=ContractType.NetPercentage.REDUCED,  # 85%
            working_time_type=ContractType.WorkingTimeType.FULL_TIME,
        )

    @pytest.fixture
    def contract_type_full(self):
        """Create a full-time contract type with 100% net percentage."""
        return ContractType.objects.create(
            name="Full-time Contract",
            symbol="HDLD",
            category=ContractType.Category.CONTRACT,
            duration_type=ContractType.DurationType.INDEFINITE,
            base_salary=Decimal("15000000"),
            net_percentage=ContractType.NetPercentage.FULL,  # 100%
            working_time_type=ContractType.WorkingTimeType.FULL_TIME,
        )

    @pytest.fixture
    def work_schedule(self):
        """Create a work schedule for weekdays."""
        # Create schedules for common weekdays to handle dynamic date tests
        schedules = []
        for weekday in [
            WorkSchedule.Weekday.MONDAY,
            WorkSchedule.Weekday.TUESDAY,
            WorkSchedule.Weekday.WEDNESDAY,
            WorkSchedule.Weekday.THURSDAY,
            WorkSchedule.Weekday.FRIDAY,
        ]:
            schedule, _ = WorkSchedule.objects.get_or_create(
                weekday=weekday,
                defaults={
                    "morning_start_time": time(8, 0),
                    "morning_end_time": time(12, 0),
                    "afternoon_start_time": time(13, 0),
                    "afternoon_end_time": time(17, 0),
                    "allowed_late_minutes": 15,
                },
            )
            schedules.append(schedule)
        return schedules[0]  # Return first one for compatibility

    def test_timesheet_is_full_salary_with_probation_contract(self, employee, contract_type_probation, work_schedule):
        """Test that timesheet entry sets is_full_salary=False when employee has 85% probation contract."""
        # Use dates relative to today to avoid expiration issues
        today = date.today()
        contract_start = today - timedelta(days=30)  # Contract started 30 days ago
        entry_date = today - timedelta(days=15)  # Entry date is 15 days ago (during contract)
        contract_end = today + timedelta(days=30)  # Contract expires in 30 days

        # Update employee type to PROBATION to match the contract intent
        employee.employee_type = EmployeeType.PROBATION
        employee.save(update_fields=["employee_type"])

        # Create an active probation contract
        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_probation,
            sign_date=contract_start,
            effective_date=contract_start,
            expiration_date=contract_end,
            status=Contract.ContractStatus.DRAFT,  # Start as DRAFT
            base_salary=Decimal("10000000"),
            net_percentage=ContractType.NetPercentage.REDUCED,  # 85%
        )

        # Change status to ACTIVE to trigger status recalculation
        contract.status = Contract.ContractStatus.ACTIVE
        contract.save()

        # Create a timesheet entry for a date when the probation contract is active
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=entry_date,
            start_time=timezone.make_aware(datetime.combine(entry_date, time(8, 0))),
            end_time=timezone.make_aware(datetime.combine(entry_date, time(17, 0))),
        )

        # Refresh from database to get updated values
        entry.refresh_from_db()

        # Assert that is_full_salary is False because of probation contract AND employee type
        assert entry.is_full_salary is False

    def test_timesheet_is_full_salary_with_full_contract(self, employee, contract_type_full, work_schedule):
        """Test that timesheet entry sets is_full_salary=True when employee has 100% full-time contract."""
        # Use dates relative to today
        from datetime import timedelta

        today = date.today()
        contract_start = today - timedelta(days=30)
        entry_date = today - timedelta(days=15)

        # Update employee type to OFFICIAL to match Full Contract
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save(update_fields=["employee_type"])

        # Create an active full-time contract
        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_full,
            sign_date=contract_start,
            effective_date=contract_start,
            expiration_date=None,  # Indefinite
            status=Contract.ContractStatus.DRAFT,
            base_salary=Decimal("15000000"),
            net_percentage=ContractType.NetPercentage.FULL,  # 100%
        )

        # Change status to ACTIVE
        contract.status = Contract.ContractStatus.ACTIVE
        contract.save()

        # Create a timesheet entry for a date when the full-time contract is active
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=entry_date,
            start_time=timezone.make_aware(datetime.combine(entry_date, time(8, 0))),
            end_time=timezone.make_aware(datetime.combine(entry_date, time(17, 0))),
        )

        # Refresh from database to get updated values
        entry.refresh_from_db()

        # Assert that is_full_salary is True because of full-time contract
        assert entry.is_full_salary is True

    def test_timesheet_is_full_salary_without_contract(self, employee, work_schedule):
        """Test that timesheet entry sets is_full_salary based on employee_type when no active contract exists.

        Per business logic: When no active contract exists, is_full_salary is True ONLY for
        UNPAID_OFFICIAL employee_type, otherwise False.
        """
        # Use dates relative to today
        from datetime import timedelta

        from apps.hrm.constants import EmployeeType

        today = date.today()
        entry_date = today - timedelta(days=15)

        # Set employee_type to UNPAID_OFFICIAL to test is_full_salary=True logic
        employee.employee_type = EmployeeType.UNPAID_OFFICIAL
        employee.save(update_fields=["employee_type"])

        # Create a timesheet entry without any contract
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=entry_date,
            start_time=timezone.make_aware(datetime.combine(entry_date, time(8, 0))),
            end_time=timezone.make_aware(datetime.combine(entry_date, time(17, 0))),
        )

        # Refresh from database to get updated values
        entry.refresh_from_db()

        # Assert that is_full_salary is True for UNPAID_OFFICIAL employee_type
        assert entry.is_full_salary is True

    def test_timesheet_is_full_salary_with_expired_probation_contract(
        self, employee, contract_type_probation, contract_type_full, work_schedule
    ):
        """Test that timesheet uses current active contract, not expired ones."""
        from datetime import timedelta

        today = date.today()
        old_date = today - timedelta(days=90)  # 90 days ago
        mid_date = today - timedelta(days=30)  # 30 days ago
        entry_date = today - timedelta(days=15)  # 15 days ago

        # Create an expired probation contract
        probation_contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_probation,
            sign_date=old_date,
            effective_date=old_date,
            expiration_date=mid_date - timedelta(days=1),  # Expired before mid_date
            status=Contract.ContractStatus.DRAFT,
            base_salary=Decimal("10000000"),
            net_percentage=ContractType.NetPercentage.REDUCED,
        )
        probation_contract.status = Contract.ContractStatus.EXPIRED
        probation_contract.save()

        # Update employee type to OFFICIAL for the new full contract
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save(update_fields=["employee_type"])

        # Create a new active full-time contract
        full_contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_full,
            sign_date=mid_date,
            effective_date=mid_date,
            expiration_date=None,
            status=Contract.ContractStatus.DRAFT,
            base_salary=Decimal("15000000"),
            net_percentage=ContractType.NetPercentage.FULL,
        )
        # Activate the contract
        full_contract.status = Contract.ContractStatus.ACTIVE
        full_contract.save()

        # Create a timesheet entry after probation period (during full-time contract)
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=entry_date,
            start_time=timezone.make_aware(datetime.combine(entry_date, time(8, 0))),
            end_time=timezone.make_aware(datetime.combine(entry_date, time(17, 0))),
        )

        # Refresh from database to get updated values
        entry.refresh_from_db()

        # Assert that is_full_salary is True because the active contract is full-time, not probation
        assert entry.is_full_salary is True
