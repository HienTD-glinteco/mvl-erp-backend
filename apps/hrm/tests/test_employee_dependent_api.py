import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Employee, EmployeeDependent

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


class EmployeeDependentAPITest(TransactionTestCase, APITestMixin):
    """Test cases for EmployeeDependent API endpoints."""

    def setUp(self):
        # Clear all existing data for clean tests
        EmployeeDependent.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department

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

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john.doe@example.com",
            phone="0900201201",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
            citizen_id="000000020012",
        )

        self.dependent_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Jane Doe",
            "relationship": "CHILD",
            "date_of_birth": "2010-05-12",
            "citizen_id": "123456789",
            "effective_date": "2024-01-01",
            "note": "Primary dependent",
        }

    def test_create_dependent(self):
        """Test creating a dependent via API."""
        url = reverse("hrm:employee-dependent-list")
        response = self.client.post(url, self.dependent_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EmployeeDependent.objects.count(), 1)

        dependent = EmployeeDependent.objects.first()
        self.assertEqual(dependent.dependent_name, self.dependent_data["dependent_name"])
        self.assertEqual(dependent.relationship, self.dependent_data["relationship"])
        self.assertEqual(dependent.citizen_id, self.dependent_data["citizen_id"])
        self.assertEqual(dependent.employee, self.employee)
        self.assertTrue(dependent.is_active)
        self.assertEqual(dependent.created_by, self.user)

        # Verify nested employee is returned in response
        result_data = self.get_response_data(response)
        self.assertIn("employee", result_data)
        self.assertEqual(result_data["employee"]["id"], self.employee.id)
        self.assertEqual(result_data["employee"]["code"], self.employee.code)
        self.assertEqual(result_data["employee"]["fullname"], self.employee.fullname)

    def test_create_dependent_minimal_fields(self):
        """Test creating a dependent with only required fields."""
        url = reverse("hrm:employee-dependent-list")
        minimal_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Bob Smith",
            "relationship": "FATHER",
            "effective_date": "2024-01-01",
        }
        response = self.client.post(url, minimal_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EmployeeDependent.objects.count(), 1)

        dependent = EmployeeDependent.objects.first()
        self.assertEqual(dependent.dependent_name, minimal_data["dependent_name"])
        self.assertEqual(dependent.relationship, minimal_data["relationship"])
        self.assertEqual(dependent.citizen_id, "")
        self.assertIsNone(dependent.date_of_birth)

    def test_create_dependent_missing_required_field(self):
        """Test creating a dependent without required fields."""
        url = reverse("hrm:employee-dependent-list")
        invalid_data = {
            "dependent_name": "Jane Doe",
            # Missing employee and relationship
        }
        response = self.client.post(url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EmployeeDependent.objects.count(), 0)

    def test_validate_citizen_id_length_9(self):
        """Test ID number validation with 9 digits."""
        url = reverse("hrm:employee-dependent-list")
        data = self.dependent_data.copy()
        data["citizen_id"] = "123456789"
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_citizen_id_length_12(self):
        """Test ID number validation with 12 digits."""
        url = reverse("hrm:employee-dependent-list")
        data = self.dependent_data.copy()
        data["citizen_id"] = "123456789012"
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_citizen_id_invalid_length(self):
        """Test ID number validation with invalid length."""
        url = reverse("hrm:employee-dependent-list")
        data = self.dependent_data.copy()
        data["citizen_id"] = "12345"  # Invalid length
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_citizen_id_non_numeric(self):
        """Test ID number validation with non-numeric characters."""
        url = reverse("hrm:employee-dependent-list")
        data = self.dependent_data.copy()
        data["citizen_id"] = "12345678A"  # Contains letter
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_dependents(self):
        """Test listing dependents."""
        # Create multiple dependents
        EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Child 1",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )
        EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Child 2",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_retrieve_dependent(self):
        """Test retrieving a specific dependent."""
        dependent = EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Jane Doe",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-detail", kwargs={"pk": dependent.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["dependent_name"], "Jane Doe")
        self.assertEqual(data["relationship"], "CHILD")

    def test_update_dependent(self):
        """Test updating a dependent."""
        dependent = EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Jane Doe",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-detail", kwargs={"pk": dependent.id})
        update_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Jane Updated",
            "relationship": "CHILD",
            "effective_date": "2024-01-01",
            "note": "Updated note",
        }
        response = self.client.put(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dependent.refresh_from_db()
        self.assertEqual(dependent.dependent_name, "Jane Updated")
        self.assertEqual(dependent.note, "Updated note")

    def test_partial_update_dependent(self):
        """Test partially updating a dependent."""
        dependent = EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Jane Doe",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-detail", kwargs={"pk": dependent.id})
        update_data = {"note": "Partial update"}
        response = self.client.patch(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dependent.refresh_from_db()
        self.assertEqual(dependent.note, "Partial update")
        self.assertEqual(dependent.dependent_name, "Jane Doe")  # Unchanged

    def test_delete_dependent(self):
        """Test soft deleting a dependent."""
        dependent = EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Jane Doe",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-detail", kwargs={"pk": dependent.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        dependent.refresh_from_db()
        self.assertFalse(dependent.is_active)  # Soft deleted

    def test_search_dependents_by_name(self):
        """Test searching dependents by name."""
        EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Alice Smith",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )
        EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Bob Jones",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-list")
        response = self.client.get(url, {"search": "Alice"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["dependent_name"], "Alice Smith")

    def test_search_dependents_by_employee_code(self):
        """Test searching dependents by employee code."""
        EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Jane Doe",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-list")
        response = self.client.get(url, {"search": self.employee.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)

    def test_filter_by_relationship(self):
        """Test filtering dependents by relationship type."""
        EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Child 1",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )
        EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Wife",
            relationship="WIFE",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-list")
        response = self.client.get(url, {"relationship": "CHILD"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["relationship"], "CHILD")

    def test_filter_by_employee(self):
        """Test filtering dependents by employee."""
        # Create another employee
        employee2 = Employee.objects.create(
            fullname="Jane Smith",
            username="janesmith",
            email="jane.smith@example.com",
            phone="0900201302",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
            citizen_id="000000020013",
        )

        EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Child 1",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )
        EmployeeDependent.objects.create(
            employee=employee2,
            dependent_name="Child 2",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-list")
        response = self.client.get(url, {"employee": self.employee.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)

    def test_ordering_by_created_at(self):
        """Test ordering dependents by created_at (default newest first)."""
        dependent1 = EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="First",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )
        dependent2 = EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Second",
            relationship="CHILD",
            effective_date="2024-01-01",
            created_by=self.user,
        )

        url = reverse("hrm:employee-dependent-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        # Newest first (default ordering is -created_at)
        self.assertEqual(data[0]["dependent_name"], "Second")
        self.assertEqual(data[1]["dependent_name"], "First")

    def test_relationship_display_field(self):
        """Test that relationship_display field is included in response."""
        url = reverse("hrm:employee-dependent-list")
        response = self.client.post(url, self.dependent_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertIn("relationship_display", data)
        self.assertEqual(data["relationship"], "CHILD")
        self.assertEqual(data["relationship_display"], "Child")
