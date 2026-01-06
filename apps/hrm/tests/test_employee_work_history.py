"""Tests for EmployeeWorkHistory model."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeWorkHistory, Position

User = get_user_model()


class EmployeeWorkHistoryModelTest(TransactionTestCase):
    """Test cases for EmployeeWorkHistory model."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        EmployeeWorkHistory.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )

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
        self.position = Position.objects.create(code="CV001", name="Senior Developer")

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_wh",
            email="johndoe_wh@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
            citizen_id="000000020201",
            attendance_code="12345",
            phone="0123456789",
            personal_email="johndoe_wh.personal@example.com",
        )

    def test_create_work_history_auto_populates_fields(self):
        """Test creating a work history record auto-populates organizational fields."""
        # Arrange
        work_history = EmployeeWorkHistory(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Promoted due to excellent performance",
        )

        # Act
        work_history.save()

        # Assert
        self.assertIsNotNone(work_history.id)
        self.assertEqual(work_history.branch, self.employee.branch)
        self.assertEqual(work_history.block, self.employee.block)
        self.assertEqual(work_history.department, self.employee.department)
        self.assertEqual(work_history.position, self.employee.position)

    def test_update_work_history_updates_organizational_fields(self):
        """Test updating a work history record updates organizational fields from employee."""
        # Arrange - Create work history
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Initial details",
        )

        # Create new organizational structure
        new_branch = Branch.objects.create(
            code="CN002",
            name="Second Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        new_block = Block.objects.create(
            code="KH002", name="Second Block", branch=new_branch, block_type=Block.BlockType.SUPPORT
        )
        new_department = Department.objects.create(
            code="PB002", name="HR Department", block=new_block, branch=new_branch
        )
        new_position = Position.objects.create(code="CV002", name="HR Manager")

        # Update employee's organizational structure
        self.employee.branch = new_branch
        self.employee.block = new_block
        self.employee.department = new_department
        self.employee.position = new_position
        self.employee.save()

        # Act - Update work history (save should re-populate from employee)
        work_history.name = EmployeeWorkHistory.EventType.TRANSFER
        work_history.save()

        # Assert
        work_history.refresh_from_db()
        self.assertEqual(work_history.branch, new_branch)
        self.assertEqual(work_history.block, new_block)
        self.assertEqual(work_history.department, new_department)
        self.assertEqual(work_history.position, new_position)

    def test_event_type_choices(self):
        """Test that event type choices are available and work correctly."""
        # Test all four event types
        event_types = [
            EmployeeWorkHistory.EventType.CHANGE_POSITION,
            EmployeeWorkHistory.EventType.CHANGE_STATUS,
            EmployeeWorkHistory.EventType.TRANSFER,
            EmployeeWorkHistory.EventType.CHANGE_CONTRACT,
        ]

        for event_type in event_types:
            work_history = EmployeeWorkHistory.objects.create(
                employee=self.employee,
                date=date(2024, 6, 1),
                name=event_type,
                detail=f"Testing {event_type}",
            )
            self.assertEqual(work_history.name, event_type)
            self.assertIsNotNone(work_history.get_name_display())

    def test_work_history_string_representation(self):
        """Test work history string representation."""
        # Arrange & Act
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Details",
        )

        # Assert
        expected = f"{work_history.name} - {self.employee} (2024-06-01)"
        self.assertEqual(str(work_history), expected)


class EmployeeWorkHistoryAPITest(TransactionTestCase):
    """Test cases for EmployeeWorkHistory API (read-only)."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        EmployeeWorkHistory.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()

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
        self.position = Position.objects.create(code="CV001", name="Senior Developer")

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_api",
            email="johndoe_api@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
            citizen_id="000000020202",
            attendance_code="12345",
            phone="0123456789",
            personal_email="johndoe_api.personal@example.com",
        )

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def test_list_work_histories(self):
        """Test listing work histories returns paginated results."""
        # Arrange
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Details 1",
        )
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 7, 1),
            name=EmployeeWorkHistory.EventType.TRANSFER,
            detail="Details 2",
        )

        # Act
        url = reverse("hrm:employee-work-history-list")
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertIn("count", response_data)
        self.assertIn("results", response_data)
        self.assertEqual(response_data["count"], 2)
        self.assertEqual(len(response_data["results"]), 2)

    def test_retrieve_work_history(self):
        """Test retrieving a single work history record."""
        # Arrange
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Promoted to senior developer",
        )

        # Act
        url = reverse("hrm:employee-work-history-detail", kwargs={"pk": work_history.id})
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["id"], work_history.id)
        self.assertEqual(response_data["name"], EmployeeWorkHistory.EventType.CHANGE_POSITION)
        self.assertIn("name_display", response_data)
        self.assertEqual(response_data["detail"], "Promoted to senior developer")
        self.assertIsNotNone(response_data["branch"])
        self.assertIsNotNone(response_data["block"])
        self.assertIsNotNone(response_data["department"])
        self.assertIsNotNone(response_data["position"])

    def test_api_create_not_allowed(self):
        """Test that creating work history via API returns 404 NotFound."""
        # Arrange
        data = {
            "employee_id": self.employee.id,
            "date": "2024-06-01",
            "name": EmployeeWorkHistory.EventType.CHANGE_POSITION,
            "detail": "Some details",
        }

        # Act
        url = reverse("hrm:employee-work-history-list")
        response = self.client.post(url, data, format="json")

        # Assert - POST returns 404 NotFound
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_partial_update_allowed(self):
        """Test that partial update (PATCH) is allowed for writable fields."""
        # Arrange
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Original details",
        )
        data = {"note": "Updated note"}

        # Act
        url = reverse("hrm:employee-work-history-detail", kwargs={"pk": work_history.id})
        response = self.client.patch(url, data, format="json")

        # Assert - PATCH should be allowed for writable fields
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        work_history.refresh_from_db()
        self.assertEqual(work_history.note, "Updated note")

    def test_api_delete_latest_record_allowed(self):
        """Test that deleting the latest work history record is allowed."""
        # Arrange
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            detail="Details",
        )

        # Act
        url = reverse("hrm:employee-work-history-detail", kwargs={"pk": work_history.id})
        response = self.client.delete(url)

        # Assert - DELETE should be allowed for the latest record
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(EmployeeWorkHistory.objects.filter(pk=work_history.id).exists())

    def test_api_delete_non_latest_record_not_allowed(self):
        """Test that deleting a non-latest work history record is not allowed."""
        # Arrange - Create two records, the first one is older
        older_record = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 5, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Older record",
        )
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            detail="Latest record",
        )

        # Act - Try to delete the older record
        url = reverse("hrm:employee-work-history-detail", kwargs={"pk": older_record.id})
        response = self.client.delete(url)

        # Assert - DELETE should not be allowed for non-latest record
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(EmployeeWorkHistory.objects.filter(pk=older_record.id).exists())

    def test_filter_by_employee(self):
        """Test filtering work histories by employee."""
        # Arrange
        employee2 = Employee.objects.create(
            fullname="Jane Smith",
            username="janesmith",
            email="janesmith@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
            citizen_id="000000020203",
            attendance_code="54321",
            phone="0987654321",
            personal_email="janesmith.personal@example.com",
        )
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Details",
        )
        EmployeeWorkHistory.objects.create(
            employee=employee2,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.TRANSFER,
            detail="Details",
        )

        # Act
        url = reverse("hrm:employee-work-history-list")
        response = self.client.get(url, {"employee": self.employee.id})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["count"], 1)
        self.assertEqual(response_data["results"][0]["name"], EmployeeWorkHistory.EventType.CHANGE_POSITION)

    def test_filter_by_date_range(self):
        """Test filtering work histories by date range."""
        # Arrange
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 1, 15),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Details",
        )
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 15),
            name=EmployeeWorkHistory.EventType.TRANSFER,
            detail="Details",
        )
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 12, 15),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            detail="Details",
        )

        # Act
        url = reverse("hrm:employee-work-history-list")
        response = self.client.get(url, {"date_from": "2024-06-01", "date_to": "2024-12-01"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["count"], 1)
        self.assertEqual(response_data["results"][0]["name"], EmployeeWorkHistory.EventType.TRANSFER)

    def test_search_work_histories(self):
        """Test searching work histories."""
        # Arrange
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            detail="Promoted to senior position",
        )
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 7, 1),
            name=EmployeeWorkHistory.EventType.TRANSFER,
            detail="Transferred to another department",
        )

        # Act
        url = reverse("hrm:employee-work-history-list")
        response = self.client.get(url, {"search": "Promoted"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["count"], 1)
        self.assertEqual(response_data["results"][0]["detail"], "Promoted to senior position")
