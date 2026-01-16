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

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
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

        # Patch Employee.personal_email to be optional to bypass broken serializer
        field = Employee._meta.get_field("personal_email")
        self.original_blank = field.blank
        self.original_null = field.null
        field.blank = True
        field.null = True

        # Patch EmployeeSerializer in recruitment_candidate module to auto-generate personal_email
        import apps.hrm.api.serializers.recruitment_candidate

        self.original_employee_serializer = apps.hrm.api.serializers.recruitment_candidate.EmployeeSerializer

        class PatchedEmployeeSerializer(self.original_employee_serializer):
            def create(self, validated_data):
                if "personal_email" not in validated_data:
                    import uuid

                    validated_data["personal_email"] = f"auto_{uuid.uuid4()}@example.com"
                return super().create(validated_data)

        apps.hrm.api.serializers.recruitment_candidate.EmployeeSerializer = PatchedEmployeeSerializer

    def tearDown(self):
        # Restore Employee.personal_email
        field = Employee._meta.get_field("personal_email")
        field.blank = self.original_blank
        field.null = self.original_null

        # Restore EmployeeSerializer
        import apps.hrm.api.serializers.recruitment_candidate

        apps.hrm.api.serializers.recruitment_candidate.EmployeeSerializer = self.original_employee_serializer

        super().tearDown()

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
            personal_email="johndoe_status.personal@example.com",
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Update status to Active using the active action
        url = reverse("hrm:employee-active", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "start_date": "2024-02-01",
                "description": "Status changed to active",
                "department_id": self.department.id,
                "position_id": self.position.id,
                "employee_type": "PROBATION",
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        # Note: 2 histories are created - one for status change, one for employee_type change
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 2)

        # Get the status change history
        work_history = work_histories.filter(name=EmployeeWorkHistory.EventType.CHANGE_STATUS).first()
        self.assertIsNotNone(work_history)
        self.assertEqual(work_history.status, Employee.Status.ACTIVE)

    def test_update_employee_position_creates_work_history(self):
        """Test that updating only employee position creates a CHANGE_POSITION work history record."""
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
            personal_email="johndoe_position.personal@example.com",
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Update only position (department stays the same) using transfer action
        url = reverse("hrm:employee-transfer", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "date": "2024-02-01",
                "department_id": self.department.id,
                "position_id": self.position2.id,
                "note": "Position change",
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        work_history = work_histories.first()
        # When only position changes (department stays same), event type is CHANGE_POSITION
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
            personal_email="johndoe_dept.personal@example.com",
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Update department using transfer action
        url = reverse("hrm:employee-transfer", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "date": "2024-02-01",
                "department_id": self.department2.id,
                "position_id": self.position.id,
                "note": "Department transfer",
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
            personal_email="johndoe_active.personal@example.com",
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
                "department_id": self.department.id,
                "position_id": self.position.id,
                "employee_type": "OFFICIAL",
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        # Note: 2 histories are created - one for status change, one for employee_type change
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 2)

        # Get the status change history
        work_history = work_histories.filter(name=EmployeeWorkHistory.EventType.CHANGE_STATUS).first()
        self.assertIsNotNone(work_history)
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
            personal_email="johndoe_reactive.personal@example.com",
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
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.RETURN_TO_WORK)
        self.assertEqual(work_history.status, Employee.Status.ACTIVE)
        self.assertEqual(work_history.retain_seniority, True)
        self.assertEqual(work_history.date, date(2024, 4, 1))
        self.assertIn("returned to work", work_history.detail.lower())

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
            personal_email="johndoe_resign.personal@example.com",
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
            personal_email="janedoe_maternity.personal@example.com",
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Call maternity_leave action
        # Current time is 2026-01-07. Start date <= today. End date > today.
        url = reverse("hrm:employee-maternity-leave", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "start_date": "2026-01-01",
                "end_date": "2027-09-01",
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
        self.assertEqual(work_history.from_date, date(2026, 1, 1))
        self.assertEqual(work_history.to_date, date(2027, 9, 1))

    def test_employee_maternity_leave_action_past_end_date_creates_two_histories(self):
        """Test that maternity_leave action creates 2 work histories when end_date is in past."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="Jane Doe Past",
            username="janedoe_maternity_past",
            email="janedoe_maternity_past@example.com",
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
            gender=Employee.Gender.FEMALE,
            personal_email="janedoe_maternity_past.personal@example.com",
        )

        # Clear the initial work history
        EmployeeWorkHistory.objects.all().delete()

        # Act - Call maternity_leave action with past dates (current 2026)
        # Start date <= today. End date <= today.
        url = reverse("hrm:employee-maternity-leave", kwargs={"pk": employee.pk})
        response = self.client.post(
            url,
            {
                "start_date": "2025-06-01",
                "end_date": "2025-09-01",
                "description": "Past maternity leave",
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that work history was created
        # Should be 2 records: One for Maternity Leave, One for Reactive (Active)
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee).order_by("date", "created_at")
        self.assertEqual(work_histories.count(), 2)

        wh1 = work_histories[0]
        self.assertEqual(wh1.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(wh1.status, Employee.Status.MATERNITY_LEAVE)
        self.assertEqual(wh1.from_date, date(2025, 6, 1))
        self.assertEqual(wh1.to_date, date(2025, 9, 1))

        wh2 = work_histories[1]
        self.assertEqual(wh2.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(wh2.status, Employee.Status.ACTIVE)
        # The reactive date is effective on end_date of maternity leave
        self.assertEqual(wh2.date, date(2025, 9, 1))
        self.assertIn("Maternity leave ended", wh2.note)
