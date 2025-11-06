"""Tests for employee work history integration with employee operations."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeWorkHistory,
    Position,
    RecruitmentCandidate,
    RecruitmentRequest,
)

User = get_user_model()


class EmployeeWorkHistoryIntegrationTest(TransactionTestCase):
    """Test cases for work history integration with employee operations."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        EmployeeWorkHistory.objects.all().delete()
        Employee.objects.all().delete()
        RecruitmentCandidate.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Main Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001", name="Main Block", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="PB001", name="Engineering Department", block=self.block, branch=self.branch
        )
        self.department2 = Department.objects.create(
            code="PB002", name="HR Department", block=self.block, branch=self.branch
        )
        self.position = Position.objects.create(code="CV001", name="Senior Developer")
        self.position2 = Position.objects.create(code="CV002", name="HR Manager")

    def test_create_employee_creates_work_history(self):
        """Test that creating an employee creates an initial work history record."""
        # Arrange
        employee_data = {
            "fullname": "Jane Smith",
            "username": "janesmith",
            "email": "janesmith@example.com",
            "department_id": self.department.id,
            "start_date": "2024-01-01",
            "attendance_code": "123456",
            "status": Employee.Status.ONBOARDING,
            "citizen_id": "123456789012",
            "phone": "0123456789",
        }

        # Act
        url = reverse("hrm:employee-list")
        response = self.client.post(url, employee_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        employee = Employee.objects.get(email="janesmith@example.com")

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(work_history.status, Employee.Status.ONBOARDING)
        self.assertEqual(work_history.date, date(2024, 1, 1))

    def test_update_employee_status_creates_work_history(self):
        """Test that updating employee status creates a work history record."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_status",
            email="johndoe_status@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000020202",
            attendance_code="12346",
            phone="0123456788",
            status=Employee.Status.ONBOARDING,
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Update status to Active
        url = reverse("hrm:employee-detail", kwargs={"pk": employee.pk})
        response = self.client.patch(
            url,
            {
                "department_id": self.department.id,
                "status": Employee.Status.ACTIVE,
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(work_history.status, Employee.Status.ACTIVE)

    def test_update_employee_position_creates_work_history(self):
        """Test that updating employee position creates a work history record."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_position",
            email="johndoe_position@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000020203",
            attendance_code="12347",
            phone="0123456787",
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Update position
        url = reverse("hrm:employee-detail", kwargs={"pk": employee.pk})
        response = self.client.patch(
            url,
            {
                "department_id": self.department.id,
                "position_id": self.position2.id,
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_POSITION)
        self.assertIn("Senior Developer", work_history.detail)
        self.assertIn("HR Manager", work_history.detail)

    def test_update_employee_department_creates_transfer_history(self):
        """Test that updating employee department creates a transfer work history record."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_dept",
            email="johndoe_dept@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000020204",
            attendance_code="12348",
            phone="0123456786",
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Update department
        url = reverse("hrm:employee-detail", kwargs={"pk": employee.pk})
        response = self.client.patch(
            url,
            {
                "department_id": self.department2.id,
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.TRANSFER)
        self.assertIn("Engineering Department", work_history.detail)
        self.assertIn("HR Department", work_history.detail)

    def test_employee_active_action_creates_work_history(self):
        """Test that the active action creates a work history record."""
        # Arrange - Create employee in onboarding status
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_active",
            email="johndoe_active@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000020205",
            attendance_code="12349",
            phone="0123456785",
            status=Employee.Status.ONBOARDING,
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Call active action
        url = reverse("hrm:employee-active", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "start_date": "2024-02-01",
                "description": "Completed onboarding",
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(work_history.status, Employee.Status.ACTIVE)
        self.assertEqual(work_history.date, date(2024, 2, 1))
        self.assertEqual(work_history.note, "Completed onboarding")

    def test_employee_reactive_action_creates_work_history(self):
        """Test that the reactive action creates a work history record with seniority flag."""
        # Arrange - Create employee in resigned status
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_reactive",
            email="johndoe_reactive@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000020206",
            attendance_code="12350",
            phone="0123456784",
            status=Employee.Status.RESIGNED,
            resignation_start_date=date(2024, 3, 1),
            resignation_reason=Employee.ResignationReason.VOLUNTARY_PERSONAL,
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Call reactive action
        url = reverse("hrm:employee-reactive", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "start_date": "2024-04-01",
                "is_seniority_retained": True,
                "description": "Returning to work",
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(work_history.status, Employee.Status.ACTIVE)
        self.assertEqual(work_history.retain_seniority, True)
        self.assertEqual(work_history.date, date(2024, 4, 1))
        self.assertIn("Reactivated", work_history.detail)

    def test_employee_resigned_action_creates_work_history(self):
        """Test that the resigned action creates a work history record with resignation reason."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_resign",
            email="johndoe_resign@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000020207",
            attendance_code="12351",
            phone="0123456783",
            status=Employee.Status.ACTIVE,
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Call resigned action
        url = reverse("hrm:employee-resigned", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "start_date": "2024-05-01",
                "resignation_reason": Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
                "description": "Moving to another company",
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(work_history.status, Employee.Status.RESIGNED)
        self.assertEqual(work_history.resignation_reason, Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE)
        self.assertEqual(work_history.from_date, date(2024, 5, 1))

    def test_employee_maternity_leave_action_creates_work_history(self):
        """Test that the maternity_leave action creates a work history record with dates."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="Jane Doe",
            username="janedoe_maternity",
            email="janedoe_maternity@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000020208",
            attendance_code="12352",
            phone="0123456782",
            status=Employee.Status.ACTIVE,
            gender=Employee.Gender.FEMALE,
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Call maternity_leave action
        url = reverse("hrm:employee-maternity-leave", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "start_date": "2024-06-01",
                "end_date": "2024-09-01",
                "description": "Maternity leave period",
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(work_history.status, Employee.Status.MATERNITY_LEAVE)
        self.assertEqual(work_history.from_date, date(2024, 6, 1))
        self.assertEqual(work_history.to_date, date(2024, 9, 1))

    def test_employee_copy_creates_work_history(self):
        """Test that copying an employee creates a work history record for the copy."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_copy_orig",
            email="johndoe_copy_orig@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000020209",
            attendance_code="12353",
            phone="0123456781",
            status=Employee.Status.ACTIVE,
        )

        # Act - Call copy action
        url = reverse("hrm:employee-copy", kwargs={"pk": employee.pk})
        response = self.client.post(url, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the copied employee - parse from JSON response
        import json

        response_data = json.loads(response.content)

        # The response should contain the data in a 'data' field due to envelope wrapping
        if "data" in response_data:
            copied_employee = Employee.objects.get(pk=response_data["data"]["id"])
        else:
            copied_employee = Employee.objects.get(pk=response_data["id"])

        # Check that work history was created for the copied employee
        work_histories = EmployeeWorkHistory.objects.filter(employee=copied_employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        # The note should mention the original employee's code
        self.assertTrue(employee.code in work_history.note or work_history.note.startswith("Employee copied from"))

    def test_recruitment_candidate_to_employee_creates_work_history(self):
        """Test that converting a recruitment candidate to employee creates a work history record."""
        # Arrange - Create proposer employee first
        proposer = Employee.objects.create(
            fullname="Proposer Employee",
            username="proposer_emp",
            email="proposer@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="111111111111",
            attendance_code="99999",
            phone="0999999999",
        )

        from apps.hrm.models import JobDescription, RecruitmentChannel, RecruitmentSource

        # Create recruitment channel and source
        recruitment_channel = RecruitmentChannel.objects.create(
            name="Job Website",
        )
        recruitment_source = RecruitmentSource.objects.create(
            name="LinkedIn",
        )

        # Create job description
        job_desc = JobDescription.objects.create(
            title="Backend Developer",
            position_title="Senior Backend Developer",
            responsibility="Develop backend services",
            requirement="Python, Django experience",
            benefit="Competitive salary",
            proposed_salary="1000-2000 USD",
        )

        # Create recruitment request
        recruitment_request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=job_desc,
            branch=self.branch,
            block=self.block,
            department=self.department,
            proposer=proposer,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="1000-2000 USD",
            number_of_positions=1,
        )

        candidate = RecruitmentCandidate.objects.create(
            name="Alice Johnson",
            email="alice@example.com",
            phone="0987654321",
            citizen_id="987654321098",
            recruitment_request=recruitment_request,
            recruitment_channel=recruitment_channel,
            recruitment_source=recruitment_source,
            branch=self.branch,
            block=self.block,
            department=self.department,
            submitted_date=date(2024, 3, 1),
            status="HIRED",
            onboard_date=date.today(),
        )

        # Act - Call to_employee action
        url = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate.pk})
        response = self.client.post(url, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Get the created employee
        employee = Employee.objects.get(email="alice@example.com")

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(work_history.status, Employee.Status.ONBOARDING)
        self.assertIn(candidate.code, work_history.note)
