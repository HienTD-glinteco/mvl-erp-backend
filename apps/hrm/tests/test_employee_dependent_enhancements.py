"""Tests for EmployeeDependent enhancements including code, effective_date, and tax_code."""

import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeDependent

User = get_user_model()


class EmployeeDependentEnhancementsAPITest(TransactionTestCase):
    """Test cases for EmployeeDependent enhancements."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        EmployeeDependent.objects.all().delete()
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
            username="johndoe_dep",
            email="johndoe_dep@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
            citizen_id="000000020200",
        )

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def test_create_dependent_auto_generates_code(self):
        """Test creating a dependent auto-generates code."""
        # Arrange
        dependent_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Jane Doe",
            "relationship": "CHILD",
            "date_of_birth": "2010-05-12",
        }

        # Act
        url = reverse("hrm:employee-dependent-list")
        response = self.client.post(url, dependent_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        self.assertIn("code", response_data)
        self.assertTrue(response_data["code"].startswith("ED"))

        # Verify in database
        dependent = EmployeeDependent.objects.first()
        self.assertIsNotNone(dependent)
        self.assertEqual(dependent.code, response_data["code"])

    def test_create_dependent_with_effective_date(self):
        """Test creating a dependent with effective_date."""
        # Arrange
        effective_date = date.today() - timedelta(days=30)
        dependent_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Jane Doe",
            "relationship": "CHILD",
            "date_of_birth": "2010-05-12",
            "effective_date": effective_date.isoformat(),
        }

        # Act
        url = reverse("hrm:employee-dependent-list")
        response = self.client.post(url, dependent_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify effective_date is stored
        self.assertEqual(response_data["effective_date"], effective_date.isoformat())

        # Verify in database
        dependent = EmployeeDependent.objects.first()
        self.assertEqual(dependent.effective_date, effective_date)

    def test_create_dependent_with_tax_code(self):
        """Test creating a dependent with tax_code."""
        # Arrange
        dependent_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Jane Doe",
            "relationship": "CHILD",
            "date_of_birth": "2010-05-12",
            "tax_code": "1234567890",
        }

        # Act
        url = reverse("hrm:employee-dependent-list")
        response = self.client.post(url, dependent_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify tax_code is stored
        self.assertEqual(response_data["tax_code"], "1234567890")

        # Verify in database
        dependent = EmployeeDependent.objects.first()
        self.assertEqual(dependent.tax_code, "1234567890")

    def test_create_dependent_without_optional_fields(self):
        """Test creating a dependent without optional fields (effective_date, tax_code)."""
        # Arrange
        dependent_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Jane Doe",
            "relationship": "CHILD",
        }

        # Act
        url = reverse("hrm:employee-dependent-list")
        response = self.client.post(url, dependent_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify optional fields are null/empty
        self.assertIsNone(response_data.get("effective_date"))
        self.assertEqual(response_data.get("tax_code"), "")

        # Verify in database
        dependent = EmployeeDependent.objects.first()
        self.assertIsNone(dependent.effective_date)
        self.assertEqual(dependent.tax_code, "")

    def test_dependent_code_format(self):
        """Test dependent code follows format ED{id:03d}."""
        # Create dependent
        dependent = EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Test Dependent",
            relationship="CHILD",
        )

        # Verify code format
        self.assertTrue(dependent.code.startswith("ED"))
        # Extract number part
        number_part = dependent.code[2:]
        self.assertTrue(number_part.isdigit())
        self.assertGreaterEqual(len(number_part), 3)

    def test_multiple_dependents_unique_codes(self):
        """Test multiple dependents get unique codes."""
        dependents = []
        for i in range(3):
            dep = EmployeeDependent.objects.create(
                employee=self.employee,
                dependent_name=f"Test Dependent {i}",
                relationship="CHILD",
            )
            dependents.append(dep)

        # Verify all codes are unique
        codes = [dep.code for dep in dependents]
        self.assertEqual(len(codes), len(set(codes)))

        # Verify all codes start with ED
        for code in codes:
            self.assertTrue(code.startswith("ED"))

    def test_code_is_read_only_in_api(self):
        """Test that code field is read-only and cannot be set via API."""
        # Arrange
        dependent_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Jane Doe",
            "relationship": "CHILD",
            "code": "CUSTOM_CODE",  # This should be ignored
        }

        # Act
        url = reverse("hrm:employee-dependent-list")
        response = self.client.post(url, dependent_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify custom code was ignored and auto-generated code was used
        self.assertNotEqual(response_data["code"], "CUSTOM_CODE")
        self.assertTrue(response_data["code"].startswith("ED"))

    def test_update_dependent_with_effective_date_and_tax_code(self):
        """Test updating a dependent with effective_date and tax_code."""
        # Create dependent
        dependent = EmployeeDependent.objects.create(
            employee=self.employee,
            dependent_name="Jane Doe",
            relationship="CHILD",
        )

        # Update with new fields
        effective_date = date.today()
        url = reverse("hrm:employee-dependent-detail", kwargs={"pk": dependent.id})
        update_data = {
            "employee_id": self.employee.id,
            "dependent_name": "Jane Doe Updated",
            "relationship": "CHILD",
            "effective_date": effective_date.isoformat(),
            "tax_code": "9876543210",
        }
        response = self.client.put(url, update_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["effective_date"], effective_date.isoformat())
        self.assertEqual(response_data["tax_code"], "9876543210")

        # Verify in database
        dependent.refresh_from_db()
        self.assertEqual(dependent.effective_date, effective_date)
        self.assertEqual(dependent.tax_code, "9876543210")
