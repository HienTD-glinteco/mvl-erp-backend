from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.core.models import Nationality, Role
from apps.files.models import FileModel
from apps.hrm.models import Block, Branch, Department, Employee, Position

User = get_user_model()


@pytest.fixture
def hr_report_patcher():
    patcher = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history.apply_async")
    mock = patcher.start()
    yield mock
    patcher.stop()


@pytest.fixture
def hr_report_delay_patcher():
    patcher = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history.delay")
    mock = patcher.start()
    yield mock
    patcher.stop()


@pytest.fixture
def recruitment_report_patcher():
    patcher = patch("apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate.apply_async")
    mock = patcher.start()
    yield mock
    patcher.stop()


@pytest.fixture
def recruitment_report_delay_patcher():
    patcher = patch("apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate.delay")
    mock = patcher.start()
    yield mock
    patcher.stop()


@pytest.fixture
def prepare_timesheet_patcher():
    patcher = patch("apps.hrm.signals.employee.prepare_monthly_timesheets.apply_async")
    mock = patcher.start()
    yield mock
    patcher.stop()


@pytest.mark.django_db
class TestEmployeeModel:
    """Test cases for Employee model"""

    @pytest.fixture(autouse=True)
    def setup_patches(self, hr_report_patcher, recruitment_report_patcher, prepare_timesheet_patcher):
        self.mock_prepare_timesheet_delay = prepare_timesheet_patcher
        # other mocks are available via fixtures but we specifically need to assert on prepare_timesheet

    def test_create_employee_assigns_default_role(self, branch, block, department):
        """Test that creating an employee assigns the default role to the user"""
        # Create a default role
        default_role = Role.objects.create(code="DEFAULT", name="Default Role", is_default_role=True)

        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456789",
        )

        assert employee.user is not None
        assert employee.user.role == default_role

    def test_create_employee_without_default_role(self, branch, block, department):
        """Test creating an employee when no default role exists"""
        # Ensure no default role exists
        Role.objects.filter(is_default_role=True).delete()

        employee = Employee.objects.create(
            fullname="Jane Doe",
            username="janedoe",
            email="jane@example.com",
            phone="0987654321",
            attendance_code="54321",
            date_of_birth="1991-01-01",
            personal_email="jane.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="987654321",
        )

        assert employee.user is not None
        assert employee.user.role is None

    def test_create_employee(self, branch, block, department):
        """Test creating an employee"""
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456789",
        )

        assert employee.code.startswith("MV")
        assert employee.fullname == "John Doe"
        assert employee.username == "johndoe"
        assert employee.email == "john@example.com"
        assert employee.user is not None
        assert employee.user.username == "johndoe"
        assert employee.user.email == "john@example.com"
        # The prepare_monthly_timesheets task should have been scheduled for new employee
        self.mock_prepare_timesheet_delay.assert_called()
        assert "John Doe" in str(employee)

    def test_delete_employee_with_user(self, branch, block, department):
        """Test deleting an employee also deletes the associated User account"""
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456789",
        )

        assert employee.user is not None
        user_id = employee.user.id
        assert User.objects.filter(id=user_id).exists()

        employee.delete()

        assert not Employee.objects.filter(id=employee.id).exists()
        assert not User.objects.filter(id=user_id).exists()

    def test_delete_employee_without_user(self, branch, block, department):
        """Test deleting an employee without an associated User account"""
        employee = Employee.objects.create(
            fullname="Jane Doe",
            username="janedoe",
            email="jane@example.com",
            phone="0987654321",
            attendance_code="54321",
            date_of_birth="1991-01-01",
            personal_email="jane.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="987654321",
        )

        if employee.user:
            user = employee.user
            employee.user = None
            employee.save()
            user.delete()

        employee_id = employee.id
        employee.delete()
        assert not Employee.objects.filter(id=employee_id).exists()

    def test_resigned_to_active_triggers_timesheet_task(self, branch, block, department):
        employee = Employee.objects.create(
            fullname="Resigned User",
            username="resigned",
            email="resigned@example.com",
            phone="0123456711",
            attendance_code="RES001",
            start_date="2020-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456900",
            resignation_start_date=timezone.now(),
            resignation_reason="Personal reasons",
            status=Employee.Status.RESIGNED,
        )

        old_status = employee.status
        employee.status = Employee.Status.ACTIVE
        employee.save(update_fields=["status"])
        employee.old_status = old_status

        self.mock_prepare_timesheet_delay.assert_called()

    def test_employee_code_unique(self, branch, block, department):
        """Test employee code uniqueness"""
        employee1 = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456789",
        )

        with pytest.raises(Exception):
            Employee.objects.create(
                code=employee1.code,
                fullname="Jane Doe",
                username="janedoe",
                email="jane@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=branch,
                block=block,
                department=department,
                citizen_id="123456780",
            )

    def test_employee_username_unique(self, branch, block, department):
        """Test that username must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456789",
        )

        with pytest.raises(Exception):
            Employee.objects.create(
                fullname="Jane Doe",
                username="johndoe",
                email="jane@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=branch,
                block=block,
                department=department,
                citizen_id="123456780",
            )

    def test_employee_email_unique(self, branch, block, department):
        """Test that email must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456789",
        )

        with pytest.raises(Exception):
            Employee.objects.create(
                fullname="Jane Doe",
                username="janedoe",
                email="john@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=branch,
                block=block,
                department=department,
                citizen_id="123456780",
            )

    def test_employee_validation_block_branch(self, branch, block, department, province, admin_unit):
        """Test validation that block must belong to branch"""
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=province,
            administrative_unit=admin_unit,
        )

        employee = Employee(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch2,
            block=block,  # This block belongs to branch, not branch2
            department=department,
        )

        employee.save()
        assert employee.branch != branch2
        assert employee.branch == department.branch

    def test_employee_validation_department_block(self, branch, block, department):
        """Test validation that department must belong to block"""
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=branch,
            block_type=Block.BlockType.SUPPORT,
        )

        employee = Employee(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block2,
            department=department,  # This department belongs to block, not block2
        )

        employee.save()
        assert employee.block != block2
        assert employee.block == department.block

    def test_employee_auto_assign_branch_block_from_department(self, branch, block, department):
        """Test that branch and block are auto-assigned from department on save"""
        employee = Employee.objects.create(
            fullname="Auto Assign Test",
            username="autotest",
            email="autotest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="autotest.personal@example.com",
            start_date="2024-01-01",
            department=department,
            citizen_id="123456789",
        )

        assert employee.branch == department.branch
        assert employee.block == department.block
        assert employee.branch == branch
        assert employee.block == block

    def test_employee_update_department_updates_branch_block(self, branch, block, department, province, admin_unit):
        """Test that changing department updates branch and block"""
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=province,
            administrative_unit=admin_unit,
        )
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=branch2,
            block_type=Block.BlockType.BUSINESS,
        )
        department2 = Department.objects.create(
            code="PB002",
            name="Test Department 2",
            branch=branch2,
            block=block2,
        )

        employee = Employee.objects.create(
            fullname="Transfer Test",
            username="transfertest",
            email="transfertest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="transfertest.personal@example.com",
            start_date="2024-01-01",
            department=department,
            citizen_id="123456789",
        )

        assert employee.branch == branch
        assert employee.block == block

        employee.department = department2
        employee.save()

        assert employee.branch == branch2
        assert employee.block == block2
        assert employee.department == department2

    def test_change_status_back_to_onboarding_fails(self, department):
        """Test that changing status back to On-boarding for an existing employee fails."""
        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            phone="1234567890",
            attendance_code="12345",
            start_date="2024-01-01",
            department=department,
            citizen_id="123456789",
        )
        employee.status = Employee.Status.ACTIVE
        employee.save(update_fields=["status"])
        employee.old_status = employee.status

        employee.status = Employee.Status.ONBOARDING
        with pytest.raises(ValidationError):
            employee.clean()

    def test_resignation_reasons_are_updated(self):
        """Test that ResignationReason choices have been updated"""
        expected_reasons = [
            "AGREEMENT_TERMINATION",
            "PROBATION_FAIL",
            "JOB_ABANDONMENT",
            "DISCIPLINARY_TERMINATION",
            "WORKFORCE_REDUCTION",
            "UNDERPERFORMING",
            "CONTRACT_EXPIRED",
            "VOLUNTARY_HEALTH",
            "VOLUNTARY_PERSONAL",
            "VOLUNTARY_CAREER_CHANGE",
            "VOLUNTARY_OTHER",
            "OTHER",
        ]
        actual_reasons = [reason.name for reason in Employee.ResignationReason]
        # Use set comparison for order independence
        assert set(expected_reasons) == set(actual_reasons)

    def test_employee_colored_code_type_property(self, department):
        """Test that colored_code_type property returns correct format"""
        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testcolor",
            email="testcolor@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testcolor.personal@example.com",
            start_date="2024-01-01",
            department=department,
            code_type=Employee.CodeType.MV,
            citizen_id="123456789",
        )

        colored_value = employee.colored_code_type
        assert colored_value is not None
        assert "value" in colored_value
        assert "variant" in colored_value
        assert colored_value["value"] == "MV"

    def test_employee_colored_status_property(self, department):
        """Test that colored_status property returns correct format"""
        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testcolor",
            email="testcolor@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testcolor.personal@example.com",
            start_date="2024-01-01",
            department=department,
            citizen_id="123456789",
        )
        employee.status = Employee.Status.ACTIVE
        employee.save(update_fields=["status"])

        colored_value = employee.colored_status
        assert colored_value is not None
        assert "value" in colored_value
        assert "variant" in colored_value
        assert colored_value["value"] == "Active"

    def test_employee_code_type_os_option(self, department):
        """Test that OS code type option can be set and retrieved"""
        employee = Employee.objects.create(
            fullname="Test Employee OS",
            username="testemployeeos",
            email="testemployeeos@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeeos.personal@example.com",
            start_date="2024-01-01",
            department=department,
            code_type=Employee.CodeType.OS,
            citizen_id="123456789",
        )

        assert employee.code_type == Employee.CodeType.OS
        assert employee.code_type.label == "OS"

    def test_employee_code_type_os_colored_property(self, department):
        """Test that colored_code_type property returns correct format for OS type with BLUE variant"""
        employee = Employee.objects.create(
            fullname="Test Employee OS Color",
            username="testemployeeoscolor",
            email="testemployeeoscolor@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeeoscolor.personal@example.com",
            start_date="2024-01-01",
            department=department,
            code_type=Employee.CodeType.OS,
            citizen_id="123456789",
        )

        colored_value = employee.colored_code_type
        assert colored_value is not None
        assert "value" in colored_value
        assert "variant" in colored_value
        assert colored_value["value"] == "OS"
        assert colored_value["variant"] == "BLUE"

    def test_employee_citizen_id_file_can_be_null(self, department):
        """Test that citizen_id_file can be null"""
        employee = Employee.objects.create(
            fullname="Test Employee No File",
            username="testemployeenofile",
            email="testemployeenofile@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeenofile.personal@example.com",
            start_date="2024-01-01",
            department=department,
            citizen_id="123456789",
            citizen_id_file=None,
        )

        assert employee.citizen_id_file is None

    def test_employee_citizen_id_file_foreign_key_relationship(self, department):
        """Test that citizen_id_file can be linked to FileModel"""
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="citizen_id_document.pdf",
            file_path="documents/citizen_ids/citizen_id_document.pdf",
            size=102400,
        )

        employee = Employee.objects.create(
            fullname="Test Employee With File",
            username="testemployeewithfile",
            email="testemployeewithfile@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeewithfile.personal@example.com",
            start_date="2024-01-01",
            department=department,
            citizen_id="123456789",
            citizen_id_file=file_instance,
        )

        assert employee.citizen_id_file is not None
        assert employee.citizen_id_file.id == file_instance.id
        assert employee.citizen_id_file.file_name == "citizen_id_document.pdf"

    def test_employee_citizen_id_file_set_null_on_delete(self, department):
        """Test that citizen_id_file is set to null when FileModel is deleted"""
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="citizen_id_to_delete.pdf",
            file_path="documents/citizen_ids/citizen_id_to_delete.pdf",
            size=102400,
        )

        employee = Employee.objects.create(
            fullname="Test Employee File Delete",
            username="testemployeefiledelete",
            email="testemployeefiledelete@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeefiledelete.personal@example.com",
            start_date="2024-01-01",
            department=department,
            citizen_id="123456789",
            citizen_id_file=file_instance,
        )

        assert employee.citizen_id_file is not None

        file_instance.delete()
        employee.refresh_from_db()
        assert employee.citizen_id_file is None

    def test_employee_phone_must_be_unique(self, branch, block, department):
        """Test that phone number must be unique across employees"""
        Employee.objects.create(
            fullname="First Employee",
            username="firstemployee",
            email="firstemployee@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="first.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="111111111111",
        )

        with pytest.raises(IntegrityError):
            Employee.objects.create(
                fullname="Second Employee",
                username="secondemployee",
                email="secondemployee@example.com",
                phone="0123456789",  # Same phone number
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="second.personal@example.com",
                start_date="2024-01-01",
                branch=branch,
                block=block,
                department=department,
                citizen_id="222222222222",
            )

    def test_employee_code_generated_with_code_type_prefix(self, branch, block, department):
        """Test that employee code is generated using code_type as prefix"""
        employee_mv = Employee.objects.create(
            fullname="MV Employee",
            username="mvemployee",
            email="mvemployee@example.com",
            phone="0123456781",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="111111111111",
            code_type=Employee.CodeType.MV,
        )
        assert employee_mv.code.startswith("MV")

        employee_ctv = Employee.objects.create(
            fullname="CTV Employee",
            username="ctvemployee",
            email="ctvemployee@example.com",
            phone="0123456782",
            attendance_code="12346",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="222222222222",
            code_type=Employee.CodeType.CTV,
        )
        assert employee_ctv.code.startswith("CTV")

        employee_os = Employee.objects.create(
            fullname="OS Employee",
            username="osemployee",
            email="osemployee@example.com",
            phone="0123456783",
            attendance_code="12347",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="333333333333",
            code_type=Employee.CodeType.OS,
        )
        assert employee_os.code.startswith("OS")


class TestEmployeeGenerateCodeFunction:
    """Test cases for the generate_code function in Employee module"""

    def test_generate_code_with_mv_code_type(self):
        """Test generate_code returns code with MV prefix"""
        from apps.hrm.models.employee import generate_code

        class MockEmployee:
            def __init__(self, id, code_type):
                self.id = id
                self.code_type = code_type
                self.code = None

            def save(self, update_fields=None):
                return None

        employee = MockEmployee(id=1, code_type="MV")
        generate_code(employee)
        assert employee.code == "MV000000001"

    def test_generate_code_with_ctv_code_type(self):
        """Test generate_code returns code with CTV prefix"""
        from apps.hrm.models.employee import generate_code

        class MockEmployee:
            def __init__(self, id, code_type):
                self.id = id
                self.code_type = code_type
                self.code = None

            def save(self, update_fields=None):
                return None

        employee = MockEmployee(id=12, code_type="CTV")
        generate_code(employee)
        assert employee.code == "CTV000000012"

    def test_generate_code_with_os_code_type(self):
        """Test generate_code returns code with OS prefix"""
        from apps.hrm.models.employee import generate_code

        class MockEmployee:
            def __init__(self, id, code_type):
                self.id = id
                self.code_type = code_type
                self.code = None

            def save(self, update_fields=None):
                return None

        employee = MockEmployee(id=444, code_type="OS")
        generate_code(employee)
        assert employee.code == "OS000000444"

    def test_generate_code_with_four_digit_id(self):
        """Test generate_code with ID >= 1000 does not pad"""
        from apps.hrm.models.employee import generate_code

        class MockEmployee:
            def __init__(self, id, code_type):
                self.id = id
                self.code_type = code_type
                self.code = None

            def save(self, update_fields=None):
                return None

        employee = MockEmployee(id=5555, code_type="MV")
        generate_code(employee)
        assert employee.code == "MV000005555"

    def test_generate_code_without_id_raises_error(self):
        """Test generate_code raises ValueError when employee has no id"""
        from apps.hrm.models.employee import generate_code

        class MockEmployee:
            def __init__(self, id, code_type):
                self.id = id
                self.code_type = code_type

        employee = MockEmployee(id=None, code_type="MV")

        with pytest.raises(ValueError) as context:
            generate_code(employee)

        assert "must have an id" in str(context.value)


@pytest.mark.django_db
class TestEmployeeAPI:
    """Test cases for Employee API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_api(self, api_client, hr_report_delay_patcher, recruitment_report_delay_patcher):
        self.client = api_client
        self.mock_hr_report_delay = hr_report_delay_patcher
        self.mock_recruitment_report_delay = recruitment_report_delay_patcher

    @pytest.fixture
    def employees(self, branch, block, department):
        emp1 = Employee.objects.create(
            fullname="John Doe",
            username="emp001",
            email="emp1@example.com",
            phone="1234567890",
            attendance_code="0000000000001",
            date_of_birth="1990-01-01",
            personal_email="emp1.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456789",
        )
        emp2 = Employee.objects.create(
            fullname="Jane Smith",
            username="emp002",
            email="emp2@example.com",
            phone="2234567890",
            attendance_code="0000000000002",
            date_of_birth="1991-01-01",
            personal_email="emp2.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456780",
        )
        emp3 = Employee.objects.create(
            fullname="Bob Johnson",
            username="emp003",
            email="emp3@example.com",
            phone="3234567890",
            attendance_code="0000000000003",
            date_of_birth="1992-01-01",
            personal_email="emp3.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456781",
        )
        return emp1, emp2, emp3

    def get_response_data(self, response):
        content = response.json()
        if "data" in content:
            data = content["data"]
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content

    def normalize_list_response(self, data):
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            count = data.get("count", len(results))
            return results, count
        if isinstance(data, list):
            return data, len(data)
        return [], 0

    def test_list_employees(self, employees):
        url = reverse("hrm:employee-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 3
        assert len(results) == 3
        codes = {item["code"] for item in results}
        assert all(code.startswith("MV") for code in codes)

    def test_filter_employees_by_code(self, employees):
        emp1 = employees[0]
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"code": emp1.code})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        assert count == 1
        assert results[0]["code"] == emp1.code

    def test_filter_employees_by_fullname(self, employees):
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"fullname": "John"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        assert count >= 1
        assert any("John" in item["fullname"] for item in results)

    def test_search_employees(self, employees):
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "Jane"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        assert count >= 1
        assert any(item["fullname"] == "Jane Smith" for item in results)

    def test_search_employees_by_citizen_id(self, branch, department):
        test_employee = Employee.objects.create(
            fullname="Test Employee",
            username="test_search_citizen",
            email="testsearch@example.com",
            phone="9876543210",
            citizen_id="987654321",
            start_date=date.today(),
            branch=branch,
            department=department,
        )

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "987654321"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        assert count >= 1
        assert any(item.get("citizen_id") == "987654321" for item in results)

    def test_list_employees_pagination(self, employees):
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"page": 1, "page_size": 2})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        # Helper returns len(results) when pagination object is stripped by get_response_data
        assert count == 2
        assert len(results) <= 2

    def test_employee_dropdown_filters_work(self, employees):
        emp2 = employees[1]
        url = reverse("hrm:employee-dropdown")
        response = self.client.get(url, {"code": emp2.code})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["code"] == emp2.code
        assert data[0]["fullname"] == "Jane Smith"

    def test_retrieve_employee(self, employees):
        emp1 = employees[0]
        nationality = Nationality.objects.create(name="Vietnam")
        emp1.nationality = nationality
        emp1.save()

        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["fullname"] == "John Doe"
        assert data["username"] == "emp001"
        assert data["email"] == "emp1@example.com"
        assert "user" in data
        assert "branch" in data
        assert "block" in data
        assert "department" in data
        assert "nationality" in data
        assert data["nationality"]["id"] == nationality.id
        assert data["nationality"]["name"] == "Vietnam"

    def test_create_employee(self, department, branch, block):
        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Alice Williams",
            "username": "emp004",
            "email": "emp4@example.com",
            "phone": "4234567890",
            "attendance_code": "58607083146091314660",
            "date_of_birth": "1993-01-01",
            "personal_email": "emp4.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": department.id,
            "note": "Test note",
            "citizen_id": "123456787",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        assert data["code"].startswith("MV")
        assert data["fullname"] == "Alice Williams"
        assert data["username"] == "emp004"
        assert data["email"] == "emp4@example.com"
        assert Employee.objects.filter(username="emp004").exists()

        employee = Employee.objects.get(username="emp004")
        assert employee.user is not None
        assert employee.user.username == "emp004"
        assert employee.branch == branch
        assert employee.block == block

    def test_update_employee(self, employees, department):
        emp1 = employees[0]
        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        payload = {
            "fullname": "John Updated",
            "username": "emp001",
            "email": "emp1@example.com",
            "phone": "9999999999",
            "attendance_code": "586070831460",
            "date_of_birth": "1990-01-01",
            "personal_email": "emp1.personal@example.com",
            "start_date": "2024-01-01",
            "citizen_id": emp1.citizen_id,
            "department_id": department.id,
        }
        response = self.client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["fullname"] == "John Updated"
        assert data["phone"] == "9999999999"

        emp1.refresh_from_db()
        assert emp1.fullname == "John Updated"
        assert emp1.phone == "9999999999"

    def test_partial_update_employee(self, employees):
        emp1 = employees[0]
        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        payload = {"fullname": "John Partially Updated"}
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["fullname"] == "John Partially Updated"

        emp1.refresh_from_db()
        assert emp1.fullname == "John Partially Updated"

    def test_delete_employee(self, employees):
        emp3 = employees[2]
        url = reverse("hrm:employee-detail", kwargs={"pk": emp3.id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Employee.objects.filter(id=emp3.id).exists()

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_create_employee_with_citizen_id_file(self, mock_s3_service_class, department):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="citizen_id_api_test.pdf",
            file_path="documents/citizen_ids/citizen_id_api_test.pdf",
            size=102400,
        )

        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Employee With Citizen ID File",
            "username": "empwithfile",
            "email": "empwithfile@example.com",
            "phone": "2139557490",
            "attendance_code": "58607083146091314661",
            "date_of_birth": "1995-01-01",
            "personal_email": "empwithfile.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": department.id,
            "citizen_id": "123456788",
            "citizen_id_file_id": file_instance.id,
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)

        assert "citizen_id_file" in data
        assert data["citizen_id_file"] is not None
        assert data["citizen_id_file"]["id"] == file_instance.id
        assert data["citizen_id_file"]["file_name"] == "citizen_id_api_test.pdf"
        assert "citizen_id_file_id" not in data

        employee = Employee.objects.get(username="empwithfile")
        assert employee.citizen_id_file is not None
        assert employee.citizen_id_file.id == file_instance.id

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_update_employee_citizen_id_file(self, mock_s3_service_class, employees, department):
        emp1 = employees[0]
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        new_file = FileModel.objects.create(
            purpose="citizen_id",
            file_name="updated_citizen_id.pdf",
            file_path="documents/citizen_ids/updated_citizen_id.pdf",
            size=204800,
        )

        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        payload = {
            "fullname": emp1.fullname,
            "username": emp1.username,
            "email": emp1.email,
            "phone": emp1.phone,
            "attendance_code": emp1.attendance_code,
            "date_of_birth": str(emp1.date_of_birth),
            "personal_email": emp1.personal_email,
            "start_date": str(emp1.start_date),
            "department_id": department.id,
            "citizen_id": emp1.citizen_id,
            "citizen_id_file_id": new_file.id,
        }
        response = self.client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert "citizen_id_file" in data
        assert data["citizen_id_file"] is not None
        assert data["citizen_id_file"]["id"] == new_file.id
        assert data["citizen_id_file"]["file_name"] == "updated_citizen_id.pdf"

        emp1.refresh_from_db()
        assert emp1.citizen_id_file is not None
        assert emp1.citizen_id_file.id == new_file.id

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_partial_update_employee_citizen_id_file(self, mock_s3_service_class, employees):
        emp2 = employees[1]
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="partial_update_citizen_id.pdf",
            file_path="documents/citizen_ids/partial_update_citizen_id.pdf",
            size=153600,
        )

        url = reverse("hrm:employee-detail", kwargs={"pk": emp2.id})
        payload = {
            "citizen_id_file_id": file_instance.id,
        }
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert "citizen_id_file" in data
        assert data["citizen_id_file"] is not None
        assert data["citizen_id_file"]["id"] == file_instance.id

        emp2.refresh_from_db()
        assert emp2.citizen_id_file is not None
        assert emp2.citizen_id_file.id == file_instance.id

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_get_employee_with_citizen_id_file(self, mock_s3_service_class, employees):
        emp1 = employees[0]
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="get_test_citizen_id.pdf",
            file_path="documents/citizen_ids/get_test_citizen_id.pdf",
            size=122880,
        )
        emp1.citizen_id_file = file_instance
        emp1.save(update_fields=["citizen_id_file"])

        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert "citizen_id_file" in data
        assert data["citizen_id_file"] is not None
        assert data["citizen_id_file"]["id"] == file_instance.id
        assert data["citizen_id_file"]["file_name"] == "get_test_citizen_id.pdf"
        assert data["citizen_id_file"]["size"] == 122880
        assert data["citizen_id_file"]["file_path"] == "documents/citizen_ids/get_test_citizen_id.pdf"

        assert "view_url" in data["citizen_id_file"]
        assert "download_url" in data["citizen_id_file"]
        assert "created_at" in data["citizen_id_file"]
        assert "updated_at" in data["citizen_id_file"]

    def test_update_employee_remove_citizen_id_file(self, employees):
        emp1 = employees[0]
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="to_be_removed.pdf",
            file_path="documents/citizen_ids/to_be_removed.pdf",
            size=102400,
        )
        emp1.citizen_id_file = file_instance
        emp1.save(update_fields=["citizen_id_file"])
        assert emp1.citizen_id_file is not None

        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        payload = {
            "citizen_id_file_id": None,
        }
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["citizen_id_file"] is None

        emp1.refresh_from_db()
        assert emp1.citizen_id_file is None

    def test_create_employee_invalid_block(self, province, admin_unit):
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=province,
            administrative_unit=admin_unit,
        )
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=branch2,
            block_type=Block.BlockType.BUSINESS,
        )
        department2 = Department.objects.create(
            code="PB002",
            name="Test Department 2",
            branch=branch2,
            block=block2,
        )

        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Test Employee",
            "username": "testuser",
            "email": "testuser@example.com",
            "phone": "5555555555",
            "attendance_code": "586070831460",
            "date_of_birth": "1994-01-01",
            "personal_email": "testuser.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": department2.id,
            "citizen_id": "123456788",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)

        employee = Employee.objects.get(username="testuser")
        assert employee.branch == branch2
        assert employee.block == block2
        assert employee.department == department2

    def test_update_employee_to_resigned_without_fields_fails(self, employees, department):
        emp1 = employees[0]
        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        payload = {
            "fullname": emp1.fullname,
            "username": emp1.username,
            "email": emp1.email,
            "phone": emp1.phone,
            "attendance_code": emp1.attendance_code,
            "date_of_birth": "1990-01-01",
            "personal_email": emp1.personal_email,
            "start_date": "2024-01-01",
            "department_id": department.id,
            "status": "Resigned",
            "citizen_id": emp1.citizen_id,
        }
        response = self.client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.json()
        assert "error" in content

    def test_retrieve_employee_includes_colored_values(self, employees):
        emp1 = employees[0]
        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert "colored_code_type" in data
        assert data["colored_code_type"] is not None
        assert "value" in data["colored_code_type"]
        assert "variant" in data["colored_code_type"]

        assert "colored_status" in data
        assert data["colored_status"] is not None
        assert "value" in data["colored_status"]
        assert "variant" in data["colored_status"]

    def test_list_employees_includes_colored_values(self, employees):
        url = reverse("hrm:employee-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count > 0
        for item in results:
            assert "colored_code_type" in item
            assert "colored_status" in item

    def test_create_employee_with_position(self, department):
        position = Position.objects.create(code="POS001", name="Test Position")

        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Employee With Position",
            "username": "emp_with_pos",
            "email": "emp_with_pos@example.com",
            "phone": "6666666666",
            "attendance_code": "586070831460",
            "date_of_birth": "1995-01-01",
            "personal_email": "emp_with_pos.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": department.id,
            "position_id": position.id,
            "citizen_id": "123456790",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)

        assert "position" in data
        assert data["position"] is not None
        assert data["position"]["id"] == position.id
        assert data["position"]["name"] == "Test Position"

        employee = Employee.objects.get(username="emp_with_pos")
        assert employee.position.id == position.id

    def test_serializer_returns_nested_objects_for_read(self, employees, branch, block, department):
        emp1 = employees[0]
        url = reverse("hrm:employee-detail", kwargs={"pk": emp1.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert "branch" in data
        assert isinstance(data["branch"], dict)
        assert data["branch"]["id"] == branch.id

        assert "block" in data
        assert isinstance(data["block"], dict)
        assert data["block"]["id"] == block.id

        assert "department" in data
        assert isinstance(data["department"], dict)
        assert data["department"]["id"] == department.id

        assert "user" in data
        assert isinstance(data["user"], dict)

    def test_create_employee_without_date_of_birth(self, branch, block, department):
        employee = Employee.objects.create(
            fullname="Jane Doe",
            username="janedoe",
            email="jane@example.com",
            phone="0123456788",
            attendance_code="12346",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456791",
        )
        assert employee.date_of_birth is None
        assert employee.fullname == "Jane Doe"
        assert employee.email == "jane@example.com"

    def test_create_employee_without_personal_email(self, branch, block, department):
        employee = Employee.objects.create(
            fullname="Bob Smith",
            username="bobsmith",
            email="bob@example.com",
            phone="0123456787",
            attendance_code="12347",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456792",
        )
        assert employee.personal_email is None
        assert employee.fullname == "Bob Smith"
        assert employee.email == "bob@example.com"

    def test_create_employee_with_optional_fields(self, branch, block, department):
        employee = Employee.objects.create(
            fullname="Alice Johnson",
            username="alicejohnson",
            email="alice@example.com",
            phone="0123456786",
            attendance_code="12348",
            date_of_birth="1995-05-15",
            personal_email="alice.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456782",
        )
        assert str(employee.date_of_birth) == "1995-05-15"
        assert employee.personal_email == "alice.personal@example.com"
        assert employee.fullname == "Alice Johnson"

    def test_create_multiple_employees_without_personal_email(self, branch, block, department):
        employee1 = Employee.objects.create(
            fullname="Charlie Brown",
            username="charliebrown",
            email="charlie@example.com",
            phone="0123456785",
            attendance_code="12349",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456783",
        )

        employee2 = Employee.objects.create(
            fullname="David Green",
            username="davidgreen",
            email="david@example.com",
            phone="0123456784",
            attendance_code="12350",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456784",
        )

        assert employee1.personal_email is None
        assert employee2.personal_email is None
        assert Employee.objects.filter(personal_email__isnull=True).count() >= 2

    def test_is_onboarding_email_sent_default(self, branch, block, department):
        employee = Employee.objects.create(
            fullname="Emily White",
            username="emilywhite",
            email="emily@example.com",
            phone="0123456783",
            attendance_code="12351",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456785",
        )
        assert employee.is_onboarding_email_sent is False

    def test_is_onboarding_email_sent_can_be_updated(self, branch, block, department):
        employee = Employee.objects.create(
            fullname="Frank Black",
            username="frankblack",
            email="frank@example.com",
            phone="0123456782",
            attendance_code="12352",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456786",
        )
        assert employee.is_onboarding_email_sent is False

        employee.is_onboarding_email_sent = True
        employee.save()
        employee.refresh_from_db()
        assert employee.is_onboarding_email_sent is True


@pytest.mark.django_db
class TestEmployeeFilter:
    """Test cases for Employee API filters"""

    @pytest.fixture(autouse=True)
    def setup_api(self, api_client, hr_report_delay_patcher, recruitment_report_delay_patcher):
        self.client = api_client
        self.mock_hr_report_delay = hr_report_delay_patcher
        self.mock_recruitment_report_delay = recruitment_report_delay_patcher

    @pytest.fixture
    def positions(self):
        leadership_position = Position.objects.create(
            name="Manager",
            code="MGR",
            is_leadership=True,
        )
        regular_position = Position.objects.create(
            name="Staff",
            code="STF",
            is_leadership=False,
        )
        return leadership_position, regular_position

    @pytest.fixture
    def employees_data(self, branch, block, department, positions):
        leadership_position, regular_position = positions

        leader_employee = Employee.objects.create(
            fullname="Leader One",
            username="leader001",
            email="leader1@example.com",
            phone="1111111111",
            attendance_code="LDR001",
            date_of_birth=date(1985, 3, 15),
            start_date=date(2020, 1, 1),
            branch=branch,
            block=block,
            department=department,
            position=leadership_position,
            is_onboarding_email_sent=True,
            citizen_id="123456789",
        )

        staff_employee = Employee.objects.create(
            fullname="Staff One",
            username="staff001",
            email="staff1@example.com",
            phone="2222222222",
            attendance_code="STF001",
            date_of_birth=date(1990, 3, 20),
            start_date=date(2021, 1, 1),
            branch=branch,
            block=block,
            department=department,
            position=regular_position,
            is_onboarding_email_sent=False,
            citizen_id="123456780",
        )

        onboarding_employee = Employee.objects.create(
            fullname="Onboarding Employee",
            username="onboarding001",
            email="onboarding1@example.com",
            phone="3333333333",
            attendance_code="ONB001",
            date_of_birth=date(1992, 6, 10),
            start_date=date(2024, 1, 1),
            branch=branch,
            block=block,
            department=department,
            position=regular_position,
            is_onboarding_email_sent=True,
            citizen_id="123456781",
        )

        march_birthday_employee = Employee.objects.create(
            fullname="March Birthday",
            username="march001",
            email="march1@example.com",
            phone="4444444444",
            attendance_code="MAR001",
            date_of_birth=date(1988, 3, 5),
            start_date=date(2019, 1, 1),
            branch=branch,
            block=block,
            department=department,
            position=leadership_position,
            is_onboarding_email_sent=False,
            citizen_id="123456782",
        )

        # Link a citizen ID file to the leader employee for filter tests
        leader_citizen_id_file = FileModel.objects.create(
            purpose="citizen_id",
            file_name="leader_citizen_id.pdf",
            file_path="documents/citizen_ids/leader_citizen_id.pdf",
            size=1024,
        )
        leader_employee.citizen_id_file = leader_citizen_id_file
        leader_employee.save(update_fields=["citizen_id_file"])

        os_employee = Employee.objects.create(
            fullname="OS Employee",
            username="os001",
            email="os1@example.com",
            phone="5555555555",
            attendance_code="OS001",
            date_of_birth=date(1991, 5, 15),
            start_date=date(2022, 1, 1),
            branch=branch,
            block=block,
            department=department,
            position=regular_position,
            code_type=Employee.CodeType.OS,
            citizen_id="123456783",
        )

        ctv_employee = Employee.objects.create(
            fullname="CTV Employee",
            username="ctv001",
            email="ctv1@example.com",
            phone="6666666666",
            attendance_code="CTV001",
            date_of_birth=date(1993, 7, 20),
            start_date=date(2023, 1, 1),
            branch=branch,
            block=block,
            department=department,
            position=regular_position,
            code_type=Employee.CodeType.CTV,
            citizen_id="123456784",
        )

        return {
            "leader": leader_employee,
            "staff": staff_employee,
            "onboarding": onboarding_employee,
            "march": march_birthday_employee,
            "os": os_employee,
            "ctv": ctv_employee,
        }

    def get_response_data(self, response):
        content = response.json()
        if "data" in content:
            data = content["data"]
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content

    def normalize_list_response(self, data):
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            count = data.get("count", len(results))
            return results, count
        if isinstance(data, list):
            return data, len(data)
        return [], 0

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_invalid_branch_returns_empty(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/avatar.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/avatar.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"branch": 999999})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 0
        assert results == []

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_position_is_leadership_true(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 2
        codes = {item["code"] for item in results}
        assert employees_data["leader"].code in codes
        assert employees_data["march"].code in codes
        assert employees_data["staff"].code not in codes

    def test_filter_by_position_is_leadership_false(self, employees_data):
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "false"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 4
        codes = {item["code"] for item in results}
        assert employees_data["staff"].code in codes
        assert employees_data["onboarding"].code in codes
        assert employees_data["os"].code in codes
        assert employees_data["ctv"].code in codes

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_is_onboarding_email_sent_true(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_onboarding_email_sent": "true"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 2
        codes = {item["code"] for item in results}
        assert employees_data["leader"].code in codes
        assert employees_data["onboarding"].code in codes

    def test_filter_by_is_onboarding_email_sent_false(self, employees_data):
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_onboarding_email_sent": "false"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 4
        codes = {item["code"] for item in results}
        assert employees_data["staff"].code in codes
        assert employees_data["march"].code in codes

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_has_citizen_id_file_true(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"has_citizen_id_file": "true"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 1
        codes = {item["code"] for item in results}
        assert employees_data["leader"].code in codes

    def test_filter_by_has_citizen_id_file_false(self, employees_data):
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"has_citizen_id_file": "false"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 5
        codes = {item["code"] for item in results}
        assert employees_data["staff"].code in codes
        assert employees_data["onboarding"].code in codes

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_date_of_birth_month_march(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"date_of_birth__month": "3"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 3
        codes = {item["code"] for item in results}
        assert employees_data["leader"].code in codes
        assert employees_data["staff"].code in codes
        assert employees_data["march"].code in codes

    def test_filter_by_date_of_birth_month_june(self, employees_data):
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"date_of_birth__month": "6"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 1
        codes = {item["code"] for item in results}
        assert employees_data["onboarding"].code in codes

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_combined_filter_leadership_and_onboarding(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true", "is_onboarding_email_sent": "true"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 1
        codes = {item["code"] for item in results}
        assert employees_data["leader"].code in codes

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_combined_filter_leadership_and_birth_month(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true", "date_of_birth__month": "3"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 2
        codes = {item["code"] for item in results}
        assert employees_data["leader"].code in codes
        assert employees_data["march"].code in codes

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_citizen_id_exact(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"citizen_id": "123456789"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 1
        assert results[0]["citizen_id"] == "123456789"
        assert results[0]["code"] == employees_data["leader"].code

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_citizen_id_partial(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"citizen_id": "12345678"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 6
        citizen_ids = {item["citizen_id"] for item in results}
        assert "123456789" in citizen_ids
        assert "123456780" in citizen_ids

    def test_search_by_citizen_id(self, employees_data):
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "123456782"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 1
        assert results[0]["citizen_id"] == "123456782"
        assert results[0]["code"] == employees_data["march"].code

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_is_os_code_type_true(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_os_code_type": "true"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 1
        codes = {item["code"] for item in results}
        assert employees_data["os"].code in codes

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_is_os_code_type_false(self, mock_s3_service_class, employees_data):
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_os_code_type": "false"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        assert count == 5
        codes = {item["code"] for item in results}
        assert employees_data["os"].code not in codes
        assert employees_data["leader"].code in codes
