import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Employee, EmployeeRelationship

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class EmployeeRelationshipAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Relationship API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        EmployeeRelationship.objects.all().delete()
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
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
            citizen_id="000000020020",
        )

        self.relationship_data = {
            "employee_id": self.employee.id,
            "relative_name": "Jane Doe",
            "relation_type": "WIFE",
            "date_of_birth": "1990-05-15",
            "citizen_id": "123456789",
            "address": "123 Main Street",
            "phone": "0901234567",
            "note": "Emergency contact",
        }

    def test_create_relationship(self):
        """Test creating a relationship via API"""
        url = reverse("hrm:employee-relationship-list")
        response = self.client.post(url, self.relationship_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EmployeeRelationship.objects.count(), 1)

        relationship = EmployeeRelationship.objects.first()
        self.assertEqual(relationship.relative_name, self.relationship_data["relative_name"])
        self.assertEqual(relationship.relation_type, self.relationship_data["relation_type"])
        self.assertEqual(relationship.phone, self.relationship_data["phone"])
        self.assertEqual(relationship.citizen_id, self.relationship_data["citizen_id"])
        self.assertEqual(relationship.employee, self.employee)
        self.assertEqual(relationship.employee_code, self.employee.code)
        self.assertEqual(relationship.employee_name, self.employee.fullname)
        self.assertTrue(relationship.is_active)
        self.assertEqual(relationship.created_by, self.user)

        # Verify nested employee is returned in response
        result_data = self.get_response_data(response)
        self.assertIn("employee", result_data)
        self.assertEqual(result_data["employee"]["id"], self.employee.id)
        self.assertEqual(result_data["employee"]["code"], self.employee.code)
        self.assertEqual(result_data["employee"]["fullname"], self.employee.fullname)

    def test_create_relationship_minimal_fields(self):
        """Test creating a relationship with only required fields"""
        url = reverse("hrm:employee-relationship-list")
        minimal_data = {
            "employee_id": self.employee.id,
            "relative_name": "Bob Smith",
            "relation_type": "FATHER",
        }
        response = self.client.post(url, minimal_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EmployeeRelationship.objects.count(), 1)

        relationship = EmployeeRelationship.objects.first()
        self.assertEqual(relationship.relative_name, minimal_data["relative_name"])
        self.assertEqual(relationship.relation_type, minimal_data["relation_type"])
        self.assertEqual(relationship.citizen_id, "")
        self.assertEqual(relationship.phone, "")
        self.assertEqual(relationship.address, "")

    def test_create_relationship_missing_required_field(self):
        """Test creating a relationship without required fields"""
        url = reverse("hrm:employee-relationship-list")
        invalid_data = {
            "relative_name": "Jane Doe",
            # Missing employee and relation_type
        }
        response = self.client.post(url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EmployeeRelationship.objects.count(), 0)

    def test_validate_citizen_id_length_9(self):
        """Test national ID validation with 9 digits"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["citizen_id"] = "123456789"
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_citizen_id_length_12(self):
        """Test national ID validation with 12 digits"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["citizen_id"] = "123456789012"
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_citizen_id_invalid_length(self):
        """Test national ID validation with invalid length"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["citizen_id"] = "12345"  # Invalid length
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_citizen_id_non_numeric(self):
        """Test national ID validation with non-numeric characters"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["citizen_id"] = "12345ABC9"  # Contains letters
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_phone_local_format(self):
        """Test Vietnamese phone validation with local format (0xxxxxxxxx)"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["phone"] = "0901234567"
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_phone_international_format(self):
        """Test Vietnamese phone validation with international format (+84xxxxxxxxx)"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["phone"] = "+84901234567"
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_phone_invalid_format(self):
        """Test phone validation with invalid format"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["phone"] = "12345"  # Invalid format
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_phone_invalid_local_length(self):
        """Test phone validation with invalid local length"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["phone"] = "090123456"  # 9 digits instead of 10
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_relationships(self):
        """Test listing relationships via API"""
        # Create multiple relationships via API
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        data2 = self.relationship_data.copy()
        data2["relative_name"] = "John Smith"
        data2["relation_type"] = "FATHER"
        self.client.post(url, data2, format="json")

        # List relationships
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)

    def test_list_relationships_default_ordering(self):
        """Test that relationships are ordered by created_at descending by default"""
        url = reverse("hrm:employee-relationship-list")

        # Create first relationship
        data1 = self.relationship_data.copy()
        data1["relative_name"] = "First Relative"
        response1 = self.client.post(url, data1, format="json")
        first_id = self.get_response_data(response1)["id"]

        # Create second relationship
        data2 = self.relationship_data.copy()
        data2["relative_name"] = "Second Relative"
        response2 = self.client.post(url, data2, format="json")
        second_id = self.get_response_data(response2)["id"]

        # List should show most recent first
        list_response = self.client.get(url)
        response_data = self.get_response_data(list_response)
        self.assertEqual(response_data[0]["id"], second_id)
        self.assertEqual(response_data[1]["id"], first_id)

    def test_retrieve_relationship(self):
        """Test retrieving a single relationship via API"""
        # Create relationship
        url = reverse("hrm:employee-relationship-list")
        create_response = self.client.post(url, self.relationship_data, format="json")
        relationship_id = self.get_response_data(create_response)["id"]

        # Retrieve relationship
        detail_url = reverse("hrm:employee-relationship-detail", kwargs={"pk": relationship_id})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["id"], relationship_id)
        self.assertEqual(response_data["relative_name"], self.relationship_data["relative_name"])

    def test_update_relationship(self):
        """Test updating a relationship via API"""
        # Create relationship
        url = reverse("hrm:employee-relationship-list")
        create_response = self.client.post(url, self.relationship_data, format="json")
        relationship_id = self.get_response_data(create_response)["id"]

        # Update relationship
        update_data = self.relationship_data.copy()
        update_data["relative_name"] = "Jane Smith Updated"
        update_data["phone"] = "0909876543"
        update_data["citizen_id"] = "123456789012"

        detail_url = reverse("hrm:employee-relationship-detail", kwargs={"pk": relationship_id})
        response = self.client.put(detail_url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["relative_name"], update_data["relative_name"])
        self.assertEqual(response_data["phone"], update_data["phone"])
        self.assertEqual(response_data["citizen_id"], update_data["citizen_id"])

    def test_partial_update_relationship(self):
        """Test partially updating a relationship via API"""
        # Create relationship
        url = reverse("hrm:employee-relationship-list")
        create_response = self.client.post(url, self.relationship_data, format="json")
        relationship_id = self.get_response_data(create_response)["id"]

        # Partial update
        partial_data = {
            "relative_name": "Jane Doe Partially Updated",
            "phone": "+84909876543",
        }

        detail_url = reverse("hrm:employee-relationship-detail", kwargs={"pk": relationship_id})
        response = self.client.patch(detail_url, partial_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["relative_name"], partial_data["relative_name"])
        self.assertEqual(response_data["phone"], partial_data["phone"])
        # Other fields should remain unchanged
        self.assertEqual(response_data["relation_type"], self.relationship_data["relation_type"])
        self.assertEqual(response_data["address"], self.relationship_data["address"])

    def test_soft_delete_relationship(self):
        """Test soft deleting a relationship via API"""
        # Create relationship
        url = reverse("hrm:employee-relationship-list")
        create_response = self.client.post(url, self.relationship_data, format="json")
        relationship_id = self.get_response_data(create_response)["id"]

        # Delete relationship
        detail_url = reverse("hrm:employee-relationship-detail", kwargs={"pk": relationship_id})
        response = self.client.delete(detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify relationship still exists in DB but is marked inactive
        relationship = EmployeeRelationship.objects.get(id=relationship_id)
        self.assertFalse(relationship.is_active)

        # Verify it doesn't appear in default list
        list_response = self.client.get(url)
        response_data = self.get_response_data(list_response)
        self.assertEqual(len(response_data), 0)

    def test_filter_by_employee(self):
        """Test filtering relationships by employee"""
        # Create another employee
        employee2 = Employee.objects.create(
            fullname="Alice Johnson",
            username="alicejohnson",
            email="alice@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
            citizen_id="000000020021",
        )

        # Create relationships for both employees
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        data2 = self.relationship_data.copy()
        data2["employee_id"] = employee2.id
        data2["relative_name"] = "Bob Johnson"
        self.client.post(url, data2, format="json")

        # Filter by first employee
        response = self.client.get(url, {"employee": self.employee.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["employee"]["id"], self.employee.id)

    def test_filter_by_relation_type(self):
        """Test filtering relationships by relation type"""
        url = reverse("hrm:employee-relationship-list")

        # Create relationships with different types
        self.client.post(url, self.relationship_data, format="json")

        data2 = self.relationship_data.copy()
        data2["relative_name"] = "Parent Name"
        data2["relation_type"] = "FATHER"
        self.client.post(url, data2, format="json")

        # Filter by WIFE
        response = self.client.get(url, {"relation_type": "WIFE"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["relation_type"], "WIFE")

    def test_filter_by_is_active(self):
        """Test filtering relationships by is_active status"""
        url = reverse("hrm:employee-relationship-list")

        # Create active relationship
        create_response = self.client.post(url, self.relationship_data, format="json")
        relationship_id = self.get_response_data(create_response)["id"]

        # Soft delete it
        detail_url = reverse("hrm:employee-relationship-detail", kwargs={"pk": relationship_id})
        self.client.delete(detail_url)

        # Create another active relationship
        data2 = self.relationship_data.copy()
        data2["relative_name"] = "Active Relative"
        self.client.post(url, data2, format="json")

        # Filter for inactive relationships
        response = self.client.get(url, {"is_active": "false"})
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertFalse(response_data[0]["is_active"])

        # Filter for active relationships
        response = self.client.get(url, {"is_active": "true"})
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertTrue(response_data[0]["is_active"])

    def test_search_by_employee_code(self):
        """Test searching relationships by employee code"""
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        # Search by employee code
        response = self.client.get(url, {"search": self.employee.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)

    def test_search_by_employee_name(self):
        """Test searching relationships by employee name"""
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        # Search by employee name
        response = self.client.get(url, {"search": "John"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)

    def test_search_by_relative_name(self):
        """Test searching relationships by relative name"""
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        # Search by relative name
        response = self.client.get(url, {"search": "Jane"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)

    def test_search_by_relation_type(self):
        """Test searching relationships by relation type"""
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        # Search by relation type
        response = self.client.get(url, {"search": "WIFE"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)

    def test_ordering_by_created_at_ascending(self):
        """Test ordering relationships by created_at ascending"""
        url = reverse("hrm:employee-relationship-list")

        # Create multiple relationships
        data1 = self.relationship_data.copy()
        data1["relative_name"] = "First"
        response1 = self.client.post(url, data1, format="json")
        first_id = self.get_response_data(response1)["id"]

        data2 = self.relationship_data.copy()
        data2["relative_name"] = "Second"
        response2 = self.client.post(url, data2, format="json")
        second_id = self.get_response_data(response2)["id"]

        # Order by created_at ascending
        response = self.client.get(url, {"ordering": "created_at"})
        response_data = self.get_response_data(response)

        self.assertEqual(response_data[0]["id"], first_id)
        self.assertEqual(response_data[1]["id"], second_id)

    def test_ordering_by_relative_name(self):
        """Test ordering relationships by relative name"""
        url = reverse("hrm:employee-relationship-list")

        # Create relationships with different names
        data1 = self.relationship_data.copy()
        data1["relative_name"] = "Zoe"
        self.client.post(url, data1, format="json")

        data2 = self.relationship_data.copy()
        data2["relative_name"] = "Alice"
        self.client.post(url, data2, format="json")

        # Order by relative_name ascending
        response = self.client.get(url, {"ordering": "relative_name"})
        response_data = self.get_response_data(response)

        self.assertEqual(response_data[0]["relative_name"], "Alice")
        self.assertEqual(response_data[1]["relative_name"], "Zoe")
