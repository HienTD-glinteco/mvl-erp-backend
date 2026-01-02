import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

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


@pytest.mark.django_db
class TestEmployeeDependentAPI(APITestMixin):
    """Test cases for EmployeeDependent API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, branch, block, department, employee):
        """Set up test data"""
        self.client = api_client
        self.user = superuser
        self.branch = branch
        self.block = block
        self.department = department
        self.employee = employee

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

        assert response.status_code == status.HTTP_201_CREATED
        assert EmployeeDependent.objects.count() == 1

        dependent = EmployeeDependent.objects.first()
        assert dependent.dependent_name == self.dependent_data["dependent_name"]
        assert dependent.relationship == self.dependent_data["relationship"]
        assert dependent.citizen_id == self.dependent_data["citizen_id"]
        assert dependent.employee == self.employee
        assert dependent.is_active is True
        assert dependent.created_by == self.user

        # Verify nested employee is returned in response
        result_data = self.get_response_data(response)
        assert "employee" in result_data
        assert result_data["employee"]["id"] == self.employee.id
        assert result_data["employee"]["code"] == self.employee.code
        assert result_data["employee"]["fullname"] == self.employee.fullname

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

        assert response.status_code == status.HTTP_201_CREATED
        assert EmployeeDependent.objects.count() == 1

        dependent = EmployeeDependent.objects.first()
        assert dependent.dependent_name == minimal_data["dependent_name"]
        assert dependent.relationship == minimal_data["relationship"]
        assert dependent.citizen_id == ""
        assert dependent.date_of_birth is None

    def test_create_dependent_missing_required_field(self):
        """Test creating a dependent without required fields."""
        url = reverse("hrm:employee-dependent-list")
        invalid_data = {
            "dependent_name": "Jane Doe",
            # Missing employee and relationship
        }
        response = self.client.post(url, invalid_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert EmployeeDependent.objects.count() == 0

    def test_validate_citizen_id_length_9(self):
        """Test ID number validation with 9 digits."""
        url = reverse("hrm:employee-dependent-list")
        data = self.dependent_data.copy()
        data["citizen_id"] = "123456789"
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_validate_citizen_id_length_12(self):
        """Test ID number validation with 12 digits."""
        url = reverse("hrm:employee-dependent-list")
        data = self.dependent_data.copy()
        data["citizen_id"] = "123456789012"
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_validate_citizen_id_invalid_length(self):
        """Test ID number validation with invalid length."""
        url = reverse("hrm:employee-dependent-list")
        data = self.dependent_data.copy()
        data["citizen_id"] = "12345"  # Invalid length
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_validate_citizen_id_non_numeric(self):
        """Test ID number validation with non-numeric characters."""
        url = reverse("hrm:employee-dependent-list")
        data = self.dependent_data.copy()
        data["citizen_id"] = "12345678A"  # Contains letter
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["dependent_name"] == "Jane Doe"
        assert data["relationship"] == "CHILD"

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

        assert response.status_code == status.HTTP_200_OK
        dependent.refresh_from_db()
        assert dependent.dependent_name == "Jane Updated"
        assert dependent.note == "Updated note"

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

        assert response.status_code == status.HTTP_200_OK
        dependent.refresh_from_db()
        assert dependent.note == "Partial update"
        assert dependent.dependent_name == "Jane Doe"  # Unchanged

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

        assert response.status_code == status.HTTP_204_NO_CONTENT
        dependent.refresh_from_db()
        assert dependent.is_active is False  # Soft deleted

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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["dependent_name"] == "Alice Smith"

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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1

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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["relationship"] == "CHILD"

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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1

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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        # Newest first (default ordering is -created_at)
        assert data[0]["dependent_name"] == "Second"
        assert data[1]["dependent_name"] == "First"

    def test_relationship_display_field(self):
        """Test that relationship_display field is included in response."""
        url = reverse("hrm:employee-dependent-list")
        response = self.client.post(url, self.dependent_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        assert "relationship_display" in data
        assert data["relationship"] == "CHILD"
        assert data["relationship_display"] == "Child"
