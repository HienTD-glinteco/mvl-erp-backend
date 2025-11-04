"""Tests for EmployeeRelationship enhancements including code, occupation, and tax_code."""

import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeRelationship

User = get_user_model()


class EmployeeRelationshipEnhancementsAPITest(TransactionTestCase):
    """Test cases for EmployeeRelationship enhancements."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        EmployeeRelationship.objects.all().delete()
        Employee.objects.all().delete()
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

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_rel",
            email="johndoe_rel@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
            citizen_id="000000020300",
        )

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def test_create_relationship_auto_generates_code(self):
        """Test creating a relationship auto-generates code."""
        # Arrange
        relationship_data = {
            "employee_id": self.employee.id,
            "relative_name": "Jane Doe",
            "relation_type": "WIFE",
        }

        # Act
        url = reverse("hrm:employee-relationship-list")
        response = self.client.post(url, relationship_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        self.assertIn("code", response_data)
        self.assertTrue(response_data["code"].startswith("ER"))

        # Verify in database
        relationship = EmployeeRelationship.objects.first()
        self.assertIsNotNone(relationship)
        self.assertEqual(relationship.code, response_data["code"])

    def test_create_relationship_with_occupation(self):
        """Test creating a relationship with occupation."""
        # Arrange
        relationship_data = {
            "employee_id": self.employee.id,
            "relative_name": "Jane Doe",
            "relation_type": "WIFE",
            "occupation": "Software Engineer",
        }

        # Act
        url = reverse("hrm:employee-relationship-list")
        response = self.client.post(url, relationship_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify occupation is stored
        self.assertEqual(response_data["occupation"], "Software Engineer")

        # Verify in database
        relationship = EmployeeRelationship.objects.first()
        self.assertEqual(relationship.occupation, "Software Engineer")

    def test_create_relationship_with_tax_code(self):
        """Test creating a relationship with tax_code."""
        # Arrange
        relationship_data = {
            "employee_id": self.employee.id,
            "relative_name": "Jane Doe",
            "relation_type": "WIFE",
            "tax_code": "1234567890",
        }

        # Act
        url = reverse("hrm:employee-relationship-list")
        response = self.client.post(url, relationship_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify tax_code is stored
        self.assertEqual(response_data["tax_code"], "1234567890")

        # Verify in database
        relationship = EmployeeRelationship.objects.first()
        self.assertEqual(relationship.tax_code, "1234567890")

    def test_create_relationship_with_occupation_and_tax_code(self):
        """Test creating a relationship with both occupation and tax_code."""
        # Arrange
        relationship_data = {
            "employee_id": self.employee.id,
            "relative_name": "Jane Doe",
            "relation_type": "WIFE",
            "occupation": "Accountant",
            "tax_code": "9876543210",
        }

        # Act
        url = reverse("hrm:employee-relationship-list")
        response = self.client.post(url, relationship_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify both fields are stored
        self.assertEqual(response_data["occupation"], "Accountant")
        self.assertEqual(response_data["tax_code"], "9876543210")

        # Verify in database
        relationship = EmployeeRelationship.objects.first()
        self.assertEqual(relationship.occupation, "Accountant")
        self.assertEqual(relationship.tax_code, "9876543210")

    def test_create_relationship_without_optional_fields(self):
        """Test creating a relationship without optional fields (occupation, tax_code)."""
        # Arrange
        relationship_data = {
            "employee_id": self.employee.id,
            "relative_name": "Jane Doe",
            "relation_type": "WIFE",
        }

        # Act
        url = reverse("hrm:employee-relationship-list")
        response = self.client.post(url, relationship_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify optional fields are empty
        self.assertEqual(response_data.get("occupation"), "")
        self.assertEqual(response_data.get("tax_code"), "")

        # Verify in database
        relationship = EmployeeRelationship.objects.first()
        self.assertEqual(relationship.occupation, "")
        self.assertEqual(relationship.tax_code, "")

    def test_relationship_code_format(self):
        """Test relationship code follows format ER{id:03d}."""
        # Create relationship
        relationship = EmployeeRelationship.objects.create(
            employee=self.employee,
            relative_name="Test Relative",
            relation_type="FATHER",
        )

        # Verify code format
        self.assertTrue(relationship.code.startswith("ER"))
        # Extract number part
        number_part = relationship.code[2:]
        self.assertTrue(number_part.isdigit())
        self.assertGreaterEqual(len(number_part), 3)

    def test_multiple_relationships_unique_codes(self):
        """Test multiple relationships get unique codes."""
        relationships = []
        for i in range(3):
            rel = EmployeeRelationship.objects.create(
                employee=self.employee,
                relative_name=f"Test Relative {i}",
                relation_type="SIBLING",
            )
            relationships.append(rel)

        # Verify all codes are unique
        codes = [rel.code for rel in relationships]
        self.assertEqual(len(codes), len(set(codes)))

        # Verify all codes start with ER
        for code in codes:
            self.assertTrue(code.startswith("ER"))

    def test_code_is_read_only_in_api(self):
        """Test that code field is read-only and cannot be set via API."""
        # Arrange
        relationship_data = {
            "employee_id": self.employee.id,
            "relative_name": "Jane Doe",
            "relation_type": "WIFE",
            "code": "CUSTOM_CODE",  # This should be ignored
        }

        # Act
        url = reverse("hrm:employee-relationship-list")
        response = self.client.post(url, relationship_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify custom code was ignored and auto-generated code was used
        self.assertNotEqual(response_data["code"], "CUSTOM_CODE")
        self.assertTrue(response_data["code"].startswith("ER"))

    def test_update_relationship_with_occupation_and_tax_code(self):
        """Test updating a relationship with occupation and tax_code."""
        # Create relationship
        relationship = EmployeeRelationship.objects.create(
            employee=self.employee,
            relative_name="Jane Doe",
            relation_type="WIFE",
        )

        # Update with new fields
        url = reverse("hrm:employee-relationship-detail", kwargs={"pk": relationship.id})
        update_data = {
            "employee_id": self.employee.id,
            "relative_name": "Jane Doe Updated",
            "relation_type": "WIFE",
            "occupation": "Doctor",
            "tax_code": "1111111111",
        }
        response = self.client.put(url, update_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["occupation"], "Doctor")
        self.assertEqual(response_data["tax_code"], "1111111111")

        # Verify in database
        relationship.refresh_from_db()
        self.assertEqual(relationship.occupation, "Doctor")
        self.assertEqual(relationship.tax_code, "1111111111")

    def test_relationship_with_mother_constant(self):
        """Test creating a relationship with MOTHER (fixed typo)."""
        # Arrange
        relationship_data = {
            "employee_id": self.employee.id,
            "relative_name": "Mary Doe",
            "relation_type": "MOTHER",
        }

        # Act
        url = reverse("hrm:employee-relationship-list")
        response = self.client.post(url, relationship_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["relation_type"], "MOTHER")

        # Verify in database
        relationship = EmployeeRelationship.objects.first()
        self.assertEqual(relationship.relation_type, "MOTHER")
