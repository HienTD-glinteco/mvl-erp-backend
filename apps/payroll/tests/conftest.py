"""Shared pytest fixtures for payroll tests."""

import random
import string
from datetime import date

import pytest
from django.contrib.auth import get_user_model

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, Position
from apps.payroll.models import PenaltyTicket

User = get_user_model()


def random_code(prefix: str = "", length: int = 6):
    """Generate a random code."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{suffix}"


def random_digits(length: int) -> str:
    """Generate a numeric string with the given length."""
    return "".join(random.choices(string.digits, k=length))


@pytest.fixture
def province(db):
    """Create a test province."""
    return Province.objects.create(
        name=f"Test Province {random_code()}",
        code=random_code("P"),
    )


@pytest.fixture
def admin_unit(db, province):
    """Create a test administrative unit."""
    return AdministrativeUnit.objects.create(
        parent_province=province,
        name=f"Test Admin Unit {random_code()}",
        code=random_code("AU"),
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def branch(db, province, admin_unit):
    """Create a test branch."""
    return Branch.objects.create(
        name=f"Test Branch {random_code()}",
        code=random_code("BR"),
        province=province,
        administrative_unit=admin_unit,
    )


@pytest.fixture
def block(db, branch):
    """Create a test block."""
    return Block.objects.create(
        name=f"Test Block {random_code()}",
        code=random_code("BL"),
        branch=branch,
        block_type=Block.BlockType.BUSINESS,
    )


@pytest.fixture
def department(db, branch, block):
    """Create a test department."""
    return Department.objects.create(
        name=f"Test Department {random_code()}",
        code=random_code("D"),
        branch=branch,
        block=block,
    )


@pytest.fixture
def position(db):
    """Create a test position."""
    return Position.objects.create(
        name=f"Test Position {random_code()}",
        code=random_code("POS"),
    )


@pytest.fixture
def employee(db, branch, block, department, position):
    """Create a test employee."""
    from apps.hrm.constants import EmployeeType

    suffix = random_code(length=6)
    return Employee.objects.create(
        code=f"E{suffix}",
        fullname="John Doe",
        username=f"emp{suffix}",
        email=f"emp{suffix}@example.com",
        status=Employee.Status.ACTIVE,
        code_type=Employee.CodeType.MV,
        employee_type=EmployeeType.OFFICIAL,
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2024, 1, 1),
        attendance_code=random_digits(6),
        citizen_id=random_digits(12),
        phone=f"09{random_digits(8)}",
        personal_email=f"emp{suffix}.personal@example.com",
    )


@pytest.fixture
def user(db):
    """Create a test user."""
    username = f"user{random_code()}"
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass123",
    )


@pytest.fixture
def penalty_month():
    """Return a test month (first day)."""
    return date(2025, 11, 1)


@pytest.fixture
def penalty_ticket(db, employee, penalty_month, user):
    """Create a test penalty ticket."""
    return PenaltyTicket.objects.create(
        employee=employee,
        employee_code=employee.code,
        employee_name=employee.fullname,
        month=penalty_month,
        amount=100000,
        violation_count=1,
        violation_type=PenaltyTicket.ViolationType.UNDER_10_MINUTES,
        note="Uniform violation - missing name tag",
        created_by=user,
    )


# ========== Payroll Fixtures ==========


@pytest.fixture
def salary_config():
    """Create a salary configuration."""
    from apps.payroll.models import SalaryConfig

    config_data = {
        "insurance_contributions": {
            "social_insurance": {"employee_rate": 0.08, "employer_rate": 0.17, "salary_ceiling": 46800000},
            "health_insurance": {"employee_rate": 0.015, "employer_rate": 0.03, "salary_ceiling": 46800000},
            "unemployment_insurance": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
            "union_fee": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
            "accident_occupational_insurance": {"employee_rate": 0, "employer_rate": 0.005, "salary_ceiling": None},
        },
        "personal_income_tax": {
            "standard_deduction": 11000000,
            "dependent_deduction": 4400000,
            "progressive_levels": [
                {"up_to": 5000000, "rate": 0.05},
                {"up_to": 10000000, "rate": 0.1},
                {"up_to": 18000000, "rate": 0.15},
                {"up_to": 32000000, "rate": 0.2},
                {"up_to": 52000000, "rate": 0.25},
                {"up_to": 80000000, "rate": 0.3},
                {"up_to": None, "rate": 0.35},
            ],
        },
        "kpi_salary": {
            "apply_on": "base_salary",
            "tiers": [
                {"code": "A", "percentage": 0.1, "description": "Excellent"},
                {"code": "B", "percentage": 0.05, "description": "Good"},
                {"code": "C", "percentage": 0, "description": "Average"},
                {"code": "D", "percentage": -0.05, "description": "Below Average"},
            ],
        },
        "overtime_multipliers": {"saturday_inweek": 1.5, "sunday": 2, "holiday": 3},
        "business_progressive_salary": {
            "apply_on": "base_salary",
            "tiers": [
                {"code": "M0", "amount": 0, "criteria": []},
                {"code": "M1", "amount": 7000000, "criteria": []},
            ],
        },
    }

    return SalaryConfig.objects.create(config=config_data)


@pytest.fixture
def salary_period(salary_config):
    """Create a salary period."""
    from apps.payroll.models import SalaryPeriod

    return SalaryPeriod.objects.create(month=date(2024, 1, 1), salary_config_snapshot=salary_config.config)


@pytest.fixture
def contract(employee):
    """Create an active contract."""
    from decimal import Decimal

    from apps.hrm.models import Contract, ContractType

    # Get or create contract type
    contract_type, _ = ContractType.objects.get_or_create(code="LABOR", defaults={"name": "Labor Contract"})

    return Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        base_salary=Decimal("20000000"),
        kpi_salary=Decimal("2000000"),
        lunch_allowance=Decimal("1000000"),
        phone_allowance=Decimal("500000"),
        other_allowance=Decimal("500000"),
        sign_date=date(2024, 1, 1),
        effective_date=date(2024, 1, 1),
        status=Contract.ContractStatus.ACTIVE,
    )


@pytest.fixture
def timesheet(employee, salary_period):
    """Create a timesheet."""
    from decimal import Decimal

    from apps.hrm.models import EmployeeMonthlyTimesheet

    return EmployeeMonthlyTimesheet.objects.create(
        employee=employee,
        report_date=salary_period.month,
        month_key="202401",
        total_working_days=Decimal("22.00"),
        official_working_days=Decimal("22.00"),
        probation_working_days=Decimal("0.00"),
        tc1_overtime_hours=Decimal("0.00"),
        tc2_overtime_hours=Decimal("0.00"),
        tc3_overtime_hours=Decimal("0.00"),
    )


@pytest.fixture
def kpi_assessment_period(salary_period):
    """Create KPI assessment period."""
    from apps.payroll.models import KPIAssessmentPeriod

    # Simple KPI config snapshot
    kpi_config = {
        "grading_criteria": {
            "A": {"min_score": 90, "percentage": 0.1},
            "B": {"min_score": 80, "percentage": 0.05},
            "C": {"min_score": 70, "percentage": 0},
            "D": {"min_score": 0, "percentage": -0.05},
        }
    }

    return KPIAssessmentPeriod.objects.create(
        month=salary_period.month, finalized=True, kpi_config_snapshot=kpi_config
    )


@pytest.fixture
def kpi_assessment(employee, kpi_assessment_period):
    """Create KPI assessment."""
    from decimal import Decimal

    from apps.payroll.models import EmployeeKPIAssessment

    return EmployeeKPIAssessment.objects.create(
        employee=employee,
        period=kpi_assessment_period,
        grade_manager="C",
        total_manager_score=Decimal("80.00"),
        total_possible_score=Decimal("100.00"),
    )


@pytest.fixture
def payroll_slip(salary_period, employee):
    """Create a payroll slip."""
    from apps.payroll.models import PayrollSlip

    return PayrollSlip.objects.create(salary_period=salary_period, employee=employee)


@pytest.fixture
def payroll_slip_pending(salary_period, employee):
    """Create a pending payroll slip."""
    from apps.payroll.models import PayrollSlip

    slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee)
    slip.status = PayrollSlip.Status.PENDING
    slip.save()
    return slip


@pytest.fixture
def employee_ready(branch, block, department, position):
    """Create an employee for ready payroll slip."""
    from apps.hrm.constants import EmployeeType
    from apps.hrm.models import Employee

    suffix = random_code(length=6)
    return Employee.objects.create(
        code=f"ER{suffix}",
        fullname="Ready Employee",
        username=f"emp_ready{suffix}",
        email=f"emp_ready{suffix}@example.com",
        status=Employee.Status.ACTIVE,
        code_type=Employee.CodeType.MV,
        employee_type=EmployeeType.OFFICIAL,
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2024, 1, 1),
        attendance_code=random_digits(6),
        personal_email=f"emp_ready{suffix}.personal@example.com",
    )


@pytest.fixture
def contract_ready(employee_ready):
    """Create an active contract for ready employee."""
    from decimal import Decimal

    from apps.hrm.models import Contract, ContractType

    # Get or create contract type
    contract_type, _ = ContractType.objects.get_or_create(code="LABOR", defaults={"name": "Labor Contract"})

    return Contract.objects.create(
        employee=employee_ready,
        contract_type=contract_type,
        base_salary=Decimal("20000000"),
        kpi_salary=Decimal("2000000"),
        lunch_allowance=Decimal("1000000"),
        phone_allowance=Decimal("500000"),
        other_allowance=Decimal("500000"),
        sign_date=date(2024, 1, 1),
        effective_date=date(2024, 1, 1),
        status=Contract.ContractStatus.ACTIVE,
    )


@pytest.fixture
def timesheet_ready(employee_ready, salary_period):
    """Create a timesheet for ready employee."""
    from decimal import Decimal

    from apps.hrm.models import EmployeeMonthlyTimesheet

    return EmployeeMonthlyTimesheet.objects.create(
        employee=employee_ready,
        report_date=salary_period.month,
        month_key="202401",
        total_working_days=Decimal("22.00"),
        official_working_days=Decimal("22.00"),
        probation_working_days=Decimal("0.00"),
        tc1_overtime_hours=Decimal("0.00"),
        tc2_overtime_hours=Decimal("0.00"),
        tc3_overtime_hours=Decimal("0.00"),
    )


@pytest.fixture
def payroll_slip_ready(salary_period, employee_ready, contract_ready, timesheet_ready):
    """Create a ready payroll slip."""
    from apps.payroll.models import PayrollSlip
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

    slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee_ready)
    calculator = PayrollCalculationService(slip)
    calculator.calculate()
    return slip
