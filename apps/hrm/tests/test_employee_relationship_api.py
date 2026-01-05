import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.hrm.api.serializers import EmployeeRelationshipExportXLSXSerializer
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


@pytest.mark.django_db
class TestEmployeeRelationshipAPI(APITestMixin):
    """Test cases for Relationship API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, branch, block, department, employee):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser
        self.branch = branch
        self.block = block
        self.department = department
        self.employee = employee

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

        assert response.status_code == status.HTTP_201_CREATED
        assert EmployeeRelationship.objects.count() == 1

        relationship = EmployeeRelationship.objects.first()
        assert relationship.relative_name == self.relationship_data["relative_name"]
        assert relationship.relation_type == self.relationship_data["relation_type"]
        assert relationship.phone == self.relationship_data["phone"]
        assert relationship.citizen_id == self.relationship_data["citizen_id"]
        assert relationship.employee == self.employee
        assert relationship.employee_code == self.employee.code
        assert relationship.employee_name == self.employee.fullname
        assert relationship.is_active is True
        assert relationship.created_by == self.user

        # Verify nested employee is returned in response
        result_data = self.get_response_data(response)
        assert "employee" in result_data
        assert result_data["employee"]["id"] == self.employee.id
        assert result_data["employee"]["code"] == self.employee.code
        # In conftest, employee fullname might be different.
        # Actually it uses 'Nguyen Van A'.
        # But wait, conftest employee fixture creates an employee.
        # I should check what conftest uses.
        assert result_data["employee"]["fullname"] == self.employee.fullname

    def test_create_relationship_minimal_fields(self):
        """Test creating a relationship with only required fields"""
        url = reverse("hrm:employee-relationship-list")
        minimal_data = {
            "employee_id": self.employee.id,
            "relative_name": "Bob Smith",
            "relation_type": "FATHER",
        }
        response = self.client.post(url, minimal_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert EmployeeRelationship.objects.count() == 1

        relationship = EmployeeRelationship.objects.first()
        assert relationship.relative_name == minimal_data["relative_name"]
        assert relationship.relation_type == minimal_data["relation_type"]
        assert relationship.citizen_id == ""
        assert relationship.phone == ""
        assert relationship.address == ""

    def test_create_relationship_missing_required_field(self):
        """Test creating a relationship without required fields"""
        url = reverse("hrm:employee-relationship-list")
        invalid_data = {
            "relative_name": "Jane Doe",
            # Missing employee and relation_type
        }
        response = self.client.post(url, invalid_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert EmployeeRelationship.objects.count() == 0

    def test_validate_citizen_id_length_9(self):
        """Test national ID validation with 9 digits"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["citizen_id"] = "123456789"
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_validate_citizen_id_length_12(self):
        """Test national ID validation with 12 digits"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["citizen_id"] = "123456789012"
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_validate_citizen_id_invalid_length(self):
        """Test national ID validation with invalid length"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["citizen_id"] = "12345"  # Invalid length
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_validate_citizen_id_non_numeric(self):
        """Test national ID validation with non-numeric characters"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["citizen_id"] = "12345ABC9"  # Contains letters
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_validate_phone_local_format(self):
        """Test Vietnamese phone validation with local format (0xxxxxxxxx)"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["phone"] = "0901234567"
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_validate_phone_international_format(self):
        """Test Vietnamese phone validation with international format (+84xxxxxxxxx)"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["phone"] = "+84901234567"
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_validate_phone_invalid_format(self):
        """Test phone validation with invalid format"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["phone"] = "12345"  # Invalid format
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_validate_phone_invalid_local_length(self):
        """Test phone validation with invalid local length"""
        url = reverse("hrm:employee-relationship-list")
        data = self.relationship_data.copy()
        data["phone"] = "090123456"  # 9 digits instead of 10
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

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
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2

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
        assert response_data[0]["id"] == second_id
        assert response_data[1]["id"] == first_id

    def test_retrieve_relationship(self):
        """Test retrieving a single relationship via API"""
        # Create relationship
        url = reverse("hrm:employee-relationship-list")
        create_response = self.client.post(url, self.relationship_data, format="json")
        relationship_id = self.get_response_data(create_response)["id"]

        # Retrieve relationship
        detail_url = reverse("hrm:employee-relationship-detail", kwargs={"pk": relationship_id})
        response = self.client.get(detail_url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["id"] == relationship_id
        assert response_data["relative_name"] == self.relationship_data["relative_name"]

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

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["relative_name"] == update_data["relative_name"]
        assert response_data["phone"] == update_data["phone"]
        assert response_data["citizen_id"] == update_data["citizen_id"]

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

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["relative_name"] == partial_data["relative_name"]
        assert response_data["phone"] == partial_data["phone"]
        # Other fields should remain unchanged
        assert response_data["relation_type"] == self.relationship_data["relation_type"]
        assert response_data["address"] == self.relationship_data["address"]

    def test_soft_delete_relationship(self):
        """Test soft deleting a relationship via API"""
        # Create relationship
        url = reverse("hrm:employee-relationship-list")
        create_response = self.client.post(url, self.relationship_data, format="json")
        relationship_id = self.get_response_data(create_response)["id"]

        # Delete relationship
        detail_url = reverse("hrm:employee-relationship-detail", kwargs={"pk": relationship_id})
        response = self.client.delete(detail_url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify relationship still exists in DB but is marked inactive
        relationship = EmployeeRelationship.objects.get(id=relationship_id)
        assert relationship.is_active is False

        # Verify it doesn't appear in default list
        list_response = self.client.get(url)
        response_data = self.get_response_data(list_response)
        assert len(response_data) == 0

    def test_filter_by_employee(self):
        """Test filtering relationships by employee"""
        # Create another employee
        employee2 = Employee.objects.create(
            fullname="Alice Johnson",
            username="alicejohnson",
            email="alice@example.com",
            phone="0900202021",
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

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["employee"]["id"] == self.employee.id

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

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["relation_type"] == "WIFE"

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
        assert len(response_data) == 1
        assert response_data[0]["is_active"] is False

        # Filter for active relationships
        response = self.client.get(url, {"is_active": "true"})
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["is_active"] is True

    def test_search_by_employee_code(self):
        """Test searching relationships by employee code"""
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        # Search by employee code
        response = self.client.get(url, {"search": self.employee.code})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1

    def test_search_by_employee_name(self):
        """Test searching relationships by employee name"""
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        # Search by employee name
        response = self.client.get(url, {"search": self.employee.fullname[:4]})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1

    def test_search_by_relative_name(self):
        """Test searching relationships by relative name"""
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        # Search by relative name
        response = self.client.get(url, {"search": "Jane"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1

    def test_search_by_relation_type(self):
        """Test searching relationships by relation type"""
        url = reverse("hrm:employee-relationship-list")
        self.client.post(url, self.relationship_data, format="json")

        # Search by relation type
        response = self.client.get(url, {"search": "WIFE"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1

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

        assert response_data[0]["id"] == first_id
        assert response_data[1]["id"] == second_id

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
        assert response_data[0]["relative_name"] == "Alice"
        assert response_data[1]["relative_name"] == "Zoe"


@pytest.mark.django_db
class TestEmployeeRelationshipExportXLSXSerializer:
    """Test cases for EmployeeRelationshipExportXLSXSerializer."""

    @pytest.fixture(autouse=True)
    def setup_data(self, employee):
        """Set up test data."""
        # The employee fixture already handles creating necessary related objects (branch, block, department, etc.)
        # No need to delete objects explicitly, pytest-django's @django_db handles transaction isolation.
        self.employee = employee

        # Create test relationship
        self.relationship = EmployeeRelationship.objects.create(
            employee=self.employee,
            relative_name="Jane Doe",
            relation_type="WIFE",
            date_of_birth="1990-05-15",
            citizen_id="123456789",
            address="123 Main Street",
            phone="0901234567",
            occupation="Teacher",
            note="Emergency contact",
        )

    def test_serializer_fields(self):
        """Test that serializer has correct default fields."""
        serializer = EmployeeRelationshipExportXLSXSerializer(instance=self.relationship)
        data = serializer.data

        assert "employee_code" in data
        assert "employee_name" in data
        assert "relative_name" in data
        assert "relation_type" in data
        assert "date_of_birth" in data
        assert "citizen_id" in data
        assert "address" in data
        assert "phone" in data
        assert "occupation" in data
        assert "note" in data

    def test_relation_type_display(self):
        """Test that relation_type returns display value."""
        serializer = EmployeeRelationshipExportXLSXSerializer(instance=self.relationship)
        data = serializer.data

        # Should return translated display value, not raw enum
        assert data["relation_type"] == "Wife"

    def test_employee_code_and_name(self):
        """Test that employee_code and employee_name are correctly serialized."""
        serializer = EmployeeRelationshipExportXLSXSerializer(instance=self.relationship)
        data = serializer.data

        assert data["employee_code"] == self.employee.code
        assert data["employee_name"] == self.employee.fullname

    def test_many_serialization(self):
        """Test serialization of multiple relationships."""
        EmployeeRelationship.objects.create(
            employee=self.employee,
            relative_name="Father Doe",
            relation_type="FATHER",
            date_of_birth="1960-01-01",
        )

        relationships = EmployeeRelationship.objects.all()
        serializer = EmployeeRelationshipExportXLSXSerializer(instance=relationships, many=True)
        data = serializer.data
        assert len(data) == 2


@pytest.mark.django_db
class TestEmployeeRelationshipExportAPI(APITestMixin):
    """Test cases for Employee Relationship export API endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, employee, settings):
        """Set up test client and user."""
        settings.EXPORTER_CELERY_ENABLED = False
        # The employee fixture already handles creating necessary related objects (branch, block, department, etc.)
        # No need to delete objects explicitly, pytest-django's @django_db handles transaction isolation.
        self.client = api_client
        self.client.force_authenticate(user=superuser)
        self.user = superuser
        self.employee = employee

        # Create test relationship
        self.relationship = EmployeeRelationship.objects.create(
            employee=self.employee,
            relative_name="Jane Doe",
            relation_type="WIFE",
            date_of_birth="1990-05-15",
            citizen_id="123456789",
            address="123 Main Street",
            phone="0901234567",
            occupation="Teacher",
            note="Emergency contact",
        )

    def test_export_endpoint_exists(self):
        """Test that export endpoint exists."""
        url = reverse("hrm:employee-relationship-export")
        response = self.client.get(url, {"delivery": "direct"})

        # Should not return 404
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_export_direct_delivery(self):
        """Test export with direct file delivery."""
        url = reverse("hrm:employee-relationship-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response["Content-Disposition"]
        assert ".xlsx" in response["Content-Disposition"]

    def test_export_uses_template(self):
        """Test that export uses the xlsx_template_name."""
        url = reverse("hrm:employee-relationship-export")
        response = self.client.get(url, {"delivery": "direct"})

        # Should return a valid XLSX file
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        # The content should be valid XLSX data
        assert len(response.content) > 0


@pytest.mark.django_db
class TestEmployeeRelationshipImportHandler:
    """Test cases for Employee Relationship import handler."""

    @pytest.fixture(autouse=True)
    def setup_data(self, employee):
        """Set up test data."""
        # The employee fixture already handles creating necessary related objects (branch, block, department, etc.)
        # No need to delete objects explicitly, pytest-django's @django_db handles transaction isolation.
        self.employee = employee

    def test_import_handler_create(self):
        """Test import handler creates a new relationship."""
        from apps.hrm.import_handlers.employee_relationship import import_handler

        headers = [
            "STT",
            "Mã nhân viên",
            "Tên nhân viên",
            "Tên người thân",
            "Mối quan hệ",
            "Ngày sinh",
            "Số CMND/CCCD/Giấy khai sinh",
            "Mã số thuế",
            "Địa chỉ",
            "Số điện thoại",
            "Nghề nghiệp",
            "Ghi chú",
        ]
        row = [
            1,
            self.employee.code,
            self.employee.fullname,
            "Jane Doe",
            "Vợ",
            "1990-05-15",
            "123456789",
            "123456789",
            "123 Main Street",
            "0901234567",
            "Teacher",
            "Emergency contact",
        ]

        result = import_handler(1, row, "test_job_id", {"headers": headers})

        assert result["ok"] is True
        assert result["action"] == "created"
        assert EmployeeRelationship.objects.count() == 1

        relationship = EmployeeRelationship.objects.first()
        assert relationship.relative_name == "Jane Doe"
        assert relationship.relation_type == "WIFE"
        assert relationship.employee == self.employee

    def test_import_handler_update(self):
        """Test import handler updates an existing relationship."""
        from apps.hrm.import_handlers.employee_relationship import import_handler

        # Create existing relationship
        EmployeeRelationship.objects.create(
            employee=self.employee,
            relative_name="Jane Doe",
            relation_type="WIFE",
            address="Old Address",
        )

        headers = [
            "STT",
            "Mã nhân viên",
            "Tên nhân viên",
            "Tên người thân",
            "Mối quan hệ",
            "Ngày sinh",
            "Số CMND/CCCD/Giấy khai sinh",
            "Mã số thuế",
            "Địa chỉ",
            "Số điện thoại",
            "Nghề nghiệp",
            "Ghi chú",
        ]
        row = [
            1,
            self.employee.code,
            self.employee.fullname,
            "Jane Doe",
            "WIFE",
            "1990-05-15",
            "123456789",
            "123456789",
            "New Address",
            "0901234567",
            "Teacher",
            "Updated note",
        ]

        result = import_handler(1, row, "test_job_id", {"headers": headers})

        assert result["ok"] is True
        assert result["action"] == "updated"
        assert EmployeeRelationship.objects.count() == 1

        relationship = EmployeeRelationship.objects.first()
        assert relationship.address == "New Address"
        assert relationship.note == "Updated note"

    def test_import_handler_missing_employee_code(self):
        """Test import handler fails with missing employee code."""
        from apps.hrm.import_handlers.employee_relationship import import_handler

        headers = [
            "STT",
            "Mã nhân viên",
            "Tên nhân viên",
            "Tên người thân",
            "Mối quan hệ",
        ]
        row = [1, "", "John Doe", "Jane Doe", "Vợ"]

        result = import_handler(1, row, "test_job_id", {"headers": headers})

        assert result["ok"] is False
        assert "Employee code is required" in result["error"]

    def test_import_handler_invalid_employee_code(self):
        """Test import handler fails with invalid employee code."""
        from apps.hrm.import_handlers.employee_relationship import import_handler

        headers = [
            "STT",
            "Mã nhân viên",
            "Tên nhân viên",
            "Tên người thân",
            "Mối quan hệ",
        ]
        row = [1, "INVALID_CODE", "John Doe", "Jane Doe", "Vợ"]

        result = import_handler(1, row, "test_job_id", {"headers": headers})

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_import_handler_missing_relative_name(self):
        """Test import handler fails with missing relative name."""
        from apps.hrm.import_handlers.employee_relationship import import_handler

        headers = [
            "STT",
            "Mã nhân viên",
            "Tên nhân viên",
            "Tên người thân",
            "Mối quan hệ",
        ]
        row = [1, self.employee.code, "John Doe", "", "Vợ"]

        result = import_handler(1, row, "test_job_id", {"headers": headers})

        assert result["ok"] is False
        assert "Relative name is required" in result["error"]

    def test_import_handler_invalid_relation_type(self):
        """Test import handler fails with invalid relation type."""
        from apps.hrm.import_handlers.employee_relationship import import_handler

        headers = [
            "STT",
            "Mã nhân viên",
            "Tên nhân viên",
            "Tên người thân",
            "Mối quan hệ",
        ]
        row = [1, self.employee.code, "John Doe", "Jane Doe", "INVALID"]

        result = import_handler(1, row, "test_job_id", {"headers": headers})

        assert result["ok"] is False
        assert "Invalid relation type" in result["error"]

    def test_import_handler_invalid_citizen_id(self):
        """Test import handler fails with invalid citizen ID length."""
        from apps.hrm.import_handlers.employee_relationship import import_handler

        headers = [
            "STT",
            "Mã nhân viên",
            "Tên nhân viên",
            "Tên người thân",
            "Mối quan hệ",
            "Ngày sinh",
            "Số CMND/CCCD/Giấy khai sinh",
        ]
        row = [1, self.employee.code, "John Doe", "Jane Doe", "Vợ", "1990-05-15", "12345"]

        result = import_handler(1, row, "test_job_id", {"headers": headers})

        assert result["ok"] is False
        assert "Invalid citizen ID length" in result["error"]

    def test_import_handler_vietnamese_relation_types(self):
        """Test import handler correctly maps Vietnamese relation types."""
        from apps.hrm.import_handlers.employee_relationship import import_handler

        relation_type_mapping = {
            "Con": "CHILD",
            "Vợ": "WIFE",
            "Chồng": "HUSBAND",
            "Bố": "FATHER",
            "Mẹ": "MOTHER",
            "Khác": "OTHER",
        }

        headers = [
            "STT",
            "Mã nhân viên",
            "Tên nhân viên",
            "Tên người thân",
            "Mối quan hệ",
        ]

        for vn_type, expected_type in relation_type_mapping.items():
            # Clear relationships for each iteration to ensure clean state
            EmployeeRelationship.objects.all().delete()

            row = [1, self.employee.code, "John Doe", f"Relative for {vn_type}", vn_type]
            result = import_handler(1, row, "test_job_id", {"headers": headers})

            assert result["ok"] is True, f"Failed for relation type: {vn_type}"
            relationship = EmployeeRelationship.objects.first()
            assert relationship.relation_type == expected_type, (
                f"Expected {expected_type} for {vn_type}, got {relationship.relation_type}"
            )
