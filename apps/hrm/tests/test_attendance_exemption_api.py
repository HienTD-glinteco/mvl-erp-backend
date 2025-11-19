import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import AttendanceExemption, Block, Branch, Department, Employee, Position

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class AttendanceExemptionAPITest(TransactionTestCase, APITestMixin):
    """Test cases for AttendanceExemption API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        AttendanceExemption.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        Position.objects.all().delete()
        Province.objects.all().delete()
        AdministrativeUnit.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create Province and AdministrativeUnit for Branch
        self.province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh District",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        # Create test organizational structure
        self.branch = Branch.objects.create(
            code="HQ",
            name="Head Office",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.block = Block.objects.create(
            code="TECH",
            name="Technology",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )

        self.department = Department.objects.create(
            code="IT",
            name="Information Technology",
            function=Department.DepartmentFunction.HR_ADMIN,
            branch=self.branch,
            block=self.block,
        )

        self.position = Position.objects.create(
            code="MGR",
            name="Manager",
        )

        # Create test employees
        self.employee1 = Employee.objects.create(
            code_type=Employee.CodeType.MV,
            code="EMP001",
            fullname="John Doe",
            username="johndoe",
            email="john.doe@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            start_date=date(2024, 1, 1),
            citizen_id="001234567890",
        )

        self.employee2 = Employee.objects.create(
            code_type=Employee.CodeType.MV,
            code="EMP002",
            fullname="Jane Smith",
            username="janesmith",
            email="jane.smith@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            start_date=date(2024, 1, 1),
            citizen_id="001234567891",
        )

        # Create test exemption
        self.exemption1 = AttendanceExemption.objects.create(
            employee=self.employee1,
            effective_date=date(2025, 1, 1),
            notes="Exempt from attendance tracking",
        )

    def test_list_exemptions(self):
        """Test listing all attendance exemptions."""
        url = reverse("hrm:attendance-exemption-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["employee"]["code"], "EMP001")

    def test_retrieve_exemption(self):
        """Test retrieving a single attendance exemption."""
        url = reverse("hrm:attendance-exemption-detail", kwargs={"pk": self.exemption1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["employee"]["code"], "EMP001")
        self.assertEqual(data["employee"]["fullname"], "John Doe")
        self.assertEqual(data["effective_date"], "2025-01-01")
        self.assertEqual(data["notes"], "Exempt from attendance tracking")

    def test_create_exemption(self):
        """Test creating a new attendance exemption."""
        url = reverse("hrm:attendance-exemption-list")
        payload = {
            "employee_id": self.employee2.id,
            "effective_date": "2025-02-01",
            "notes": "Management decision",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertEqual(data["employee"]["code"], "EMP002")
        self.assertEqual(data["effective_date"], "2025-02-01")
        self.assertEqual(data["notes"], "Management decision")
        self.assertEqual(AttendanceExemption.objects.count(), 2)

    def test_create_exemption_without_effective_date(self):
        """Test creating exemption without effective_date (optional field)."""
        url = reverse("hrm:attendance-exemption-list")
        payload = {
            "employee_id": self.employee2.id,
            "notes": "No specific effective date",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertIsNone(data["effective_date"])
        self.assertEqual(data["notes"], "No specific effective date")

    def test_create_duplicate_exemption(self):
        """Test creating a duplicate exemption for the same employee."""
        url = reverse("hrm:attendance-exemption-list")
        payload = {
            "employee_id": self.employee1.id,  # Already has exemption
            "effective_date": "2025-03-01",
            "notes": "Duplicate attempt",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertFalse(content["success"])
        self.assertIn("employee_id", str(content["error"]))
        self.assertIn("already has an active exemption", str(content["error"]).lower())

    def test_create_exemption_for_inactive_employee(self):
        """Test creating exemption for inactive employee."""
        inactive_employee = Employee.objects.create(
            code_type=Employee.CodeType.MV,
            code="EMP003",
            fullname="Inactive Employee",
            username="inactive",
            email="inactive@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.RESIGNED,
            start_date=date(2024, 1, 1),
            resignation_start_date=date(2024, 12, 1),
            resignation_reason=Employee.ResignationReason.VOLUNTARY_OTHER,
            citizen_id="001234567892",
        )

        url = reverse("hrm:attendance-exemption-list")
        payload = {
            "employee_id": inactive_employee.id,
            "effective_date": "2025-04-01",
            "notes": "Should fail",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertFalse(content["success"])

    def test_update_exemption(self):
        """Test updating an attendance exemption."""
        url = reverse("hrm:attendance-exemption-detail", kwargs={"pk": self.exemption1.pk})
        payload = {
            "employee_id": self.employee1.id,
            "effective_date": "2025-02-01",
            "notes": "Updated exemption",
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["effective_date"], "2025-02-01")
        self.assertEqual(data["notes"], "Updated exemption")

    def test_partial_update_exemption(self):
        """Test partially updating an attendance exemption."""
        url = reverse("hrm:attendance-exemption-detail", kwargs={"pk": self.exemption1.pk})
        payload = {"notes": "Partially updated notes"}
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["notes"], "Partially updated notes")
        self.assertEqual(data["effective_date"], "2025-01-01")  # Unchanged

    def test_delete_exemption(self):
        """Test hard deleting an attendance exemption."""
        url = reverse("hrm:attendance-exemption-detail", kwargs={"pk": self.exemption1.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify it's completely deleted (hard delete)
        self.assertEqual(AttendanceExemption.objects.count(), 0)
        list_url = reverse("hrm:attendance-exemption-list")
        list_response = self.client.get(list_url)
        data = self.get_response_data(list_response)
        self.assertEqual(len(data), 0)

    def test_search_exemptions_by_employee_code(self):
        """Test searching exemptions by employee code."""
        url = reverse("hrm:attendance-exemption-list")
        response = self.client.get(url, {"search": "EMP001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["employee"]["code"], "EMP001")

    def test_search_exemptions_by_employee_name(self):
        """Test searching exemptions by employee name."""
        url = reverse("hrm:attendance-exemption-list")
        response = self.client.get(url, {"search": "John"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["employee"]["fullname"], "John Doe")

    def test_filter_exemptions_by_branch(self):
        """Test filtering exemptions by branch."""
        url = reverse("hrm:attendance-exemption-list")
        response = self.client.get(url, {"branch": self.branch.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)

    def test_filter_exemptions_by_position(self):
        """Test filtering exemptions by position."""
        url = reverse("hrm:attendance-exemption-list")
        response = self.client.get(url, {"position": self.position.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)

    def test_filter_exemptions_by_effective_date_range(self):
        """Test filtering exemptions by effective date range."""
        # Create another exemption with different date
        exemption2 = AttendanceExemption.objects.create(
            employee=self.employee2,
            effective_date=date(2025, 6, 1),
            notes="Mid-year exemption",
        )

        url = reverse("hrm:attendance-exemption-list")

        # Filter for dates from Jan to Mar
        response = self.client.get(
            url,
            {
                "effective_date_from": "2025-01-01",
                "effective_date_to": "2025-03-31",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["employee"]["code"], "EMP001")

    def test_ordering_by_employee_code(self):
        """Test ordering exemptions by employee code."""
        AttendanceExemption.objects.create(
            employee=self.employee2,
            effective_date=date(2025, 3, 1),
            notes="Second exemption",
        )

        url = reverse("hrm:attendance-exemption-list")
        response = self.client.get(url, {"ordering": "employee__code"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["employee"]["code"], "EMP001")
        self.assertEqual(data[1]["employee"]["code"], "EMP002")

    def test_ordering_by_effective_date(self):
        """Test ordering exemptions by effective date."""
        AttendanceExemption.objects.create(
            employee=self.employee2,
            effective_date=date(2025, 6, 1),
            notes="Later exemption",
        )

        url = reverse("hrm:attendance-exemption-list")
        response = self.client.get(url, {"ordering": "effective_date"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["effective_date"], "2025-01-01")
        self.assertEqual(data[1]["effective_date"], "2025-06-01")

    def test_employee_nested_serializer_details(self):
        """Test that employee nested serializer includes all required fields."""
        url = reverse("hrm:attendance-exemption-detail", kwargs={"pk": self.exemption1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check employee structure
        employee = data["employee"]
        self.assertIn("id", employee)
        self.assertIn("code", employee)
        self.assertIn("fullname", employee)
        self.assertIn("email", employee)
        self.assertIn("position", employee)
        self.assertIn("branch", employee)

        # Check position structure
        self.assertIsNotNone(employee["position"])
        self.assertEqual(employee["position"]["code"], "MGR")
        self.assertEqual(employee["position"]["name"], "Manager")

        # Check branch structure
        self.assertIsNotNone(employee["branch"])
        self.assertEqual(employee["branch"]["code"], "HQ")
        self.assertEqual(employee["branch"]["name"], "Head Office")
