import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Nationality
from apps.hrm.models import Block, Branch, ContractType, Department, Employee, Position

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


class EmployeeAttendanceCodeAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Employee API attendance_code field."""

    def setUp(self):
        """Set up test data."""
        # Clear existing data
        Employee.objects.all().delete()
        User.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        ContractType.objects.all().delete()
        Position.objects.all().delete()

        from apps.core.models import AdministrativeUnit, Province

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure with all required fields
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        self.branch = Branch.objects.create(
            name="Main Branch",
            code="BR001",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            name="Block A", code="BL001", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            name="IT Department", code="IT001", branch=self.branch, block=self.block
        )
        self.position = Position.objects.create(name="Developer", code="DEV001")
        self.contract_type = ContractType.objects.create(name="Full-time")

        # Create nationality if needed
        self.nationality = Nationality.objects.create(name="Vietnamese")

        self.employee_data = {
            "code_type": "MV",
            "fullname": "John Doe",
            "attendance_code": "531",
            "username": "johndoe",
            "email": "john.doe@example.com",
            "department_id": self.department.id,
            "position_id": self.position.id,
            "contract_type_id": self.contract_type.id,
            "start_date": "2025-01-01",
            "date_of_birth": "1990-01-01",
            "gender": "MALE",
            "marital_status": "SINGLE",
            "phone": "0123456789",
            "personal_email": "john.personal@example.com",
            "citizen_id": "100000000001",
        }

    def test_create_employee_with_attendance_code(self):
        """Test creating an employee with attendance_code."""
        # Act
        url = reverse("hrm:employee-list")
        response = self.client.post(url, self.employee_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Employee.objects.count(), 1)

        employee = Employee.objects.first()
        self.assertEqual(employee.attendance_code, "531")

        response_data = self.get_response_data(response)
        self.assertEqual(response_data["attendance_code"], "531")

    def test_create_employee_with_invalid_attendance_code(self):
        """Test creating an employee with invalid attendance_code (non-digits)."""
        # Arrange
        invalid_data = self.employee_data.copy()
        invalid_data["attendance_code"] = "ABC123"  # Invalid: contains letters

        # Act
        url = reverse("hrm:employee-list")
        response = self.client.post(url, invalid_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Employee.objects.count(), 0)

        # Check error message
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_retrieve_employee_with_attendance_code(self):
        """Test retrieving an employee shows attendance_code."""
        # Arrange - Create employee directly
        employee = Employee.objects.create(
            code_type="MV",
            code="MV001",
            fullname="Jane Smith",
            attendance_code="100",
            username="janesmith",
            email="jane@example.com",
            department=self.department,
            position=self.position,
            contract_type=self.contract_type,
            start_date=date(2025, 1, 1),
            date_of_birth=date(1995, 5, 15),
            phone="0987654321",
            personal_email="jane.personal@example.com",
            citizen_id="000000020005",
        )

        # Act
        url = reverse("hrm:employee-detail", kwargs={"pk": employee.id})
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["attendance_code"], "100")

    def test_update_employee_attendance_code(self):
        """Test updating an employee's attendance_code."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            code_type="MV",
            code="MV002",
            fullname="Bob Wilson",
            attendance_code="200",
            username="bobwilson",
            email="bob@example.com",
            department=self.department,
            position=self.position,
            contract_type=self.contract_type,
            start_date=date(2025, 1, 1),
            date_of_birth=date(1992, 3, 20),
            phone="0111222333",
            personal_email="bob.personal@example.com",
            citizen_id="000000020006",
        )

        update_data = {
            "code_type": "MV",
            "fullname": "Bob Wilson",
            "attendance_code": "999",  # Updated
            "username": "bobwilson",
            "email": "bob@example.com",
            "department_id": self.department.id,
            "position_id": self.position.id,
            "contract_type_id": self.contract_type.id,
            "start_date": "2025-01-01",
            "date_of_birth": "1992-03-20",
            "gender": "MALE",
            "marital_status": "SINGLE",
            "phone": "0111222333",
            "personal_email": "bob.personal@example.com",
            "citizen_id": "000000020006",
        }

        # Act
        url = reverse("hrm:employee-detail", kwargs={"pk": employee.id})
        response = self.client.put(url, update_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employee.refresh_from_db()
        self.assertEqual(employee.attendance_code, "999")

        response_data = self.get_response_data(response)
        self.assertEqual(response_data["attendance_code"], "999")

    def test_partial_update_employee_attendance_code(self):
        """Test partially updating an employee's attendance_code."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            code_type="MV",
            code="MV003",
            fullname="Alice Brown",
            attendance_code="300",
            username="alicebrown",
            email="alice@example.com",
            department=self.department,
            position=self.position,
            contract_type=self.contract_type,
            start_date=date(2025, 1, 1),
            date_of_birth=date(1993, 7, 10),
            phone="0444555666",
            personal_email="alice.personal@example.com",
            citizen_id="000000020007",
        )

        # Act - Only update attendance_code
        url = reverse("hrm:employee-detail", kwargs={"pk": employee.id})
        response = self.client.patch(url, {"attendance_code": "888"}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employee.refresh_from_db()
        self.assertEqual(employee.attendance_code, "888")
        self.assertEqual(employee.fullname, "Alice Brown")  # Unchanged

    def test_list_employees_includes_attendance_code(self):
        """Test listing employees includes attendance_code field."""
        # Arrange - Create employees
        Employee.objects.create(
            code_type="MV",
            code="MV004",
            fullname="Employee 1",
            attendance_code="401",
            username="emp1",
            email="emp1@example.com",
            department=self.department,
            position=self.position,
            start_date=date(2025, 1, 1),
            date_of_birth=date(1990, 1, 1),
            phone="0123456781",
            personal_email="emp1.personal@example.com",
            citizen_id="000000020008",
        )
        Employee.objects.create(
            code_type="MV",
            code="MV005",
            fullname="Employee 2",
            attendance_code="402",
            username="emp2",
            email="emp2@example.com",
            department=self.department,
            position=self.position,
            start_date=date(2025, 1, 1),
            date_of_birth=date(1991, 1, 1),
            phone="0123456782",
            personal_email="emp2.personal@example.com",
            citizen_id="000000020009",
        )

        # Act
        url = reverse("hrm:employee-list")
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        self.assertEqual(response_data[0]["attendance_code"], "401")
        self.assertEqual(response_data[1]["attendance_code"], "402")

    def test_search_employee_by_attendance_code(self):
        """Test searching employees by attendance_code."""
        # Arrange - Create employees
        Employee.objects.create(
            code_type="MV",
            code="MV006",
            fullname="Searchable Employee",
            attendance_code="531",
            username="searchable",
            email="searchable@example.com",
            department=self.department,
            position=self.position,
            start_date=date(2025, 1, 1),
            date_of_birth=date(1990, 1, 1),
            phone="0123456783",
            personal_email="searchable.personal@example.com",
            citizen_id="000000020010",
        )
        Employee.objects.create(
            code_type="MV",
            code="MV007",
            fullname="Other Employee",
            attendance_code="999",
            username="other",
            email="other@example.com",
            department=self.department,
            position=self.position,
            start_date=date(2025, 1, 1),
            date_of_birth=date(1991, 1, 1),
            phone="0123456784",
            personal_email="other.personal@example.com",
            citizen_id="000000020011",
        )

        # Act
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "531"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["attendance_code"], "531")

    def test_attendance_code_digits_only_validation(self):
        """Test that attendance_code accepts only digits."""
        # Arrange
        test_cases = [
            ("123", True),  # Valid: digits only
            ("0001", True),  # Valid: leading zeros
            ("12345678901234567890", True),  # Valid: long number
            ("12a3", False),  # Invalid: contains letter
            ("12-3", False),  # Invalid: contains hyphen
            ("12.3", False),  # Invalid: contains dot
            ("12 3", False),  # Invalid: contains space
            ("", False),  # Invalid: empty
        ]

        for code, should_succeed in test_cases:
            with self.subTest(code=code):
                data = self.employee_data.copy()
                data["attendance_code"] = code
                data["username"] = f"user_{code}"
                data["email"] = f"user_{code}@example.com"
                data["personal_email"] = f"user_{code}.personal@example.com"

                url = reverse("hrm:employee-list")
                response = self.client.post(url, data, format="json")

                if should_succeed:
                    self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Failed for code: {code}")
                else:
                    self.assertIn(
                        response.status_code,
                        [status.HTTP_400_BAD_REQUEST],
                        f"Should have failed for code: {code}",
                    )

                # Clean up for next iteration
                Employee.objects.all().delete()
