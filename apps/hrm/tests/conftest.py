"""Shared pytest fixtures for HRM tests."""

import pytest

from apps.core.models import AdministrativeUnit, Nationality, Province, UserDevice
from apps.files.models import FileModel
from apps.hrm.models import (
    AttendanceGeolocation,
    AttendanceWifiDevice,
    Bank,
    BankAccount,
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    Position,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)
from apps.realestate.models import Project


@pytest.fixture
def province(db):
    """Create a test province."""
    return Province.objects.create(code="01", name="Test Province")


@pytest.fixture
def user(superuser):
    """Alias for superuser for backward compatibility."""
    return superuser


@pytest.fixture
def admin_unit(db, province):
    """Create a test administrative unit."""
    return AdministrativeUnit.objects.create(
        parent_province=province,
        name="Test Admin Unit",
        code="AU01",
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def branch(db, province, admin_unit):
    """Create a test branch."""
    return Branch.objects.create(
        name="Test Branch",
        code="CN001",
        province=province,
        administrative_unit=admin_unit,
    )


@pytest.fixture
def block(db, branch):
    """Create a test block."""
    return Block.objects.create(
        name="Test Block",
        code="KH001",
        branch=branch,
        block_type=Block.BlockType.BUSINESS,
    )


@pytest.fixture
def department(db, branch, block):
    """Create a test department."""
    return Department.objects.create(
        name="Test Department",
        code="PB001",
        branch=branch,
        block=block,
        function=Department.DepartmentFunction.BUSINESS,
    )


@pytest.fixture
def position(db):
    """Create a test position."""
    return Position.objects.create(name="Test Position", code="CV001")


@pytest.fixture
def employee(db, branch, block, department, position, user):
    """Create a test employee with all required relationships."""
    return Employee.objects.create(
        user=user,
        code="MV000001",
        fullname="Test Employee",
        username="testemployee",
        email="test@example.com",
        phone="0123456789",
        attendance_code="12345",
        start_date="2024-01-01",
        branch=branch,
        block=block,
        department=department,
        position=position,
        citizen_id="123456789012",
        personal_email="test.employee@example.com",
    )


@pytest.fixture
def employee_factory(db, branch, block, department, position):
    """Factory for creating test employees."""
    from apps.core.models import User

    counter = {"value": 1}

    def create_employee(**kwargs):
        counter["value"] += 1
        num = counter["value"]

        user = User.objects.create_user(
            username=f"testuser{num}",
            email=f"test{num}@example.com",
            password="testpass123",
        )

        defaults = {
            "user": user,
            "code": f"MV{num:06d}",
            "fullname": f"Test Employee {num}",
            "username": f"testemployee{num}",
            "email": f"test{num}@example.com",
            "personal_email": f"testemployee{num}.personal@example.com",
            "phone": f"012345678{num}",
            "attendance_code": f"{12345 + num}",
            "start_date": "2024-01-01",
            "branch": branch,
            "block": block,
            "department": department,
            "position": position,
            "citizen_id": f"{123456789000 + num:012d}",
        }
        defaults.update(kwargs)
        return Employee.objects.create(**defaults)

    return create_employee


@pytest.fixture
def job_description(db):
    """Create a test job description."""
    return JobDescription.objects.create(
        title="Senior Python Developer",
        position_title="Senior Python Developer",
        responsibility="Develop backend services",
        requirement="5+ years experience",
        benefit="Competitive salary",
        proposed_salary="2000-3000 USD",
    )


@pytest.fixture
def recruitment_source(db):
    """Create a test recruitment source."""
    return RecruitmentSource.objects.create(
        name="LinkedIn",
        description="Professional networking platform",
    )


@pytest.fixture
def recruitment_request(db, job_description, department, employee):
    """Create a test recruitment request."""
    return RecruitmentRequest.objects.create(
        name="Backend Developer Position",
        job_description=job_description,
        department=department,
        proposer=employee,
        recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
        status=RecruitmentRequest.Status.OPEN,
        proposed_salary="2000-3000 USD",
        number_of_positions=2,
    )


@pytest.fixture
def recruitment_channel(db):
    """Create a test recruitment channel."""
    return RecruitmentChannel.objects.create(
        name="LinkedIn Ads",
        description="Paid advertisements on LinkedIn",
    )


@pytest.fixture
def user_device(db, user):
    """Create a test user device."""
    return UserDevice.objects.create(
        user=user,
        device_id="device123",
        platform=UserDevice.Platform.ANDROID,
    )


@pytest.fixture
def project(db):
    """Create a test project."""
    return Project.objects.create(
        name="Test Project",
        code="PRJ001",
    )


@pytest.fixture
def attendance_geolocation(db, project, user):
    """Create a test attendance geolocation."""
    from decimal import Decimal

    return AttendanceGeolocation.objects.create(
        name="Main Office",
        code="GEO001",
        project=project,
        latitude=Decimal("10.7769000"),
        longitude=Decimal("106.7009000"),
        radius_m=100,
        status=AttendanceGeolocation.Status.ACTIVE,
        created_by=user,
        updated_by=user,
    )


@pytest.fixture
def attendance_wifi_device(db):
    """Create a test attendance wifi device."""
    return AttendanceWifiDevice.objects.create(
        name="Office WiFi",
        code="WIFI001",
        bssid="00:11:22:33:44:55",
        state=AttendanceWifiDevice.State.IN_USE,
    )


@pytest.fixture
def confirmed_file(db, user):
    """Create a confirmed test file."""
    return FileModel.objects.create(
        file_name="attendance.jpg",
        file_path="attendance/attendance.jpg",
        purpose="attendance_photo",
        is_confirmed=True,
        uploaded_by=user,
    )


@pytest.fixture
def recruitment_candidate(db, recruitment_request, recruitment_source, recruitment_channel):
    """Create a test recruitment candidate."""
    from datetime import date

    return RecruitmentCandidate.objects.create(
        name="Nguyen Van B",
        citizen_id="123456789012",
        email="nguyenvanb@example.com",
        phone="0123456789",
        recruitment_request=recruitment_request,
        recruitment_source=recruitment_source,
        recruitment_channel=recruitment_channel,
        years_of_experience=5,
        submitted_date=date(2025, 10, 15),
    )


@pytest.fixture
def nationality(db):
    """Create a test nationality."""
    return Nationality.objects.create(name="Vietnamese")


@pytest.fixture
def bank(db):
    """Create a test bank."""
    return Bank.objects.create(code="VCB", name="Vietcombank")


@pytest.fixture
def bank_account(db, employee, bank):
    """Create a test bank account for an employee."""
    return BankAccount.objects.create(
        employee=employee,
        bank=bank,
        account_number="123456789",
        account_name=employee.fullname,
        is_primary=True,
    )
