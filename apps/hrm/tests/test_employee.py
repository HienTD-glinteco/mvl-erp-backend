import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Block, Branch, Department, Employee

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

    def normalize_list_response(self, data):
        """Normalize list responses that may or may not be paginated"""

        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            count = data.get("count", len(results))
            return results, count

        if isinstance(data, list):
            return data, len(data)

        return [], 0


class EmployeeModelTest(TestCase):
    """Test cases for Employee model"""

    def setUp(self):
        # Create test branch, block, and department
        from apps.core.models import AdministrativeUnit, Province

        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )
        self.department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=self.branch,
            block=self.block,
        )

    def test_create_employee(self):
        """Test creating an employee"""
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="1234567890",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertTrue(employee.code.startswith("MV"))
        self.assertEqual(employee.fullname, "John Doe")
        self.assertEqual(employee.username, "johndoe")
        self.assertEqual(employee.email, "john@example.com")
        self.assertIsNotNone(employee.user)
        self.assertEqual(employee.user.username, "johndoe")
        self.assertEqual(employee.user.email, "john@example.com")
        self.assertIn("John Doe", str(employee))

    def test_employee_code_unique(self):
        """Test employee code uniqueness"""
        employee1 = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Cannot create with same code manually
        with self.assertRaises(Exception):
            Employee.objects.create(
                code=employee1.code,
                fullname="Jane Doe",
                username="janedoe",
                email="jane@example.com",
                branch=self.branch,
                block=self.block,
                department=self.department,
            )

    def test_employee_username_unique(self):
        """Test that username must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        with self.assertRaises(Exception):
            Employee.objects.create(
                fullname="Jane Doe",
                username="johndoe",
                email="jane@example.com",
                branch=self.branch,
                block=self.block,
                department=self.department,
            )

    def test_employee_email_unique(self):
        """Test that email must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        with self.assertRaises(Exception):
            Employee.objects.create(
                fullname="Jane Doe",
                username="janedoe",
                email="john@example.com",
                branch=self.branch,
                block=self.block,
                department=self.department,
            )

    def test_employee_validation_block_branch(self):
        """Test validation that block must belong to branch"""
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        employee = Employee(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            branch=branch2,
            block=self.block,  # This block belongs to self.branch, not branch2
            department=self.department,
        )

        with self.assertRaises(Exception):
            employee.clean()

    def test_employee_validation_department_block(self):
        """Test validation that department must belong to block"""
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )

        employee = Employee(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            branch=self.branch,
            block=block2,
            department=self.department,  # This department belongs to self.block, not block2
        )

        with self.assertRaises(Exception):
            employee.clean()

    def test_employee_auto_assign_branch_block_from_department(self):
        """Test that branch and block are auto-assigned from department on save"""
        # Create employee with only department specified
        employee = Employee.objects.create(
            fullname="Auto Assign Test",
            username="autotest",
            email="autotest@example.com",
            department=self.department,
        )

        # Verify that branch and block were automatically set from department
        self.assertEqual(employee.branch, self.department.branch)
        self.assertEqual(employee.block, self.department.block)
        self.assertEqual(employee.branch, self.branch)
        self.assertEqual(employee.block, self.block)

    def test_employee_update_department_updates_branch_block(self):
        """Test that changing department updates branch and block"""
        # Create a second organizational structure
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=branch2,
            block_type=Block.BlockType.BUSINESS,
        )
        department2 = Department.objects.create(
            code="PB002",
            name="Test Department 2",
            branch=branch2,
            block=block2,
        )

        # Create employee with initial department
        employee = Employee.objects.create(
            fullname="Transfer Test",
            username="transfertest",
            email="transfertest@example.com",
            department=self.department,
        )

        # Initially should be in first branch/block
        self.assertEqual(employee.branch, self.branch)
        self.assertEqual(employee.block, self.block)

        # Update to second department
        employee.department = department2
        employee.save()

        # Should now be in second branch/block
        self.assertEqual(employee.branch, branch2)
        self.assertEqual(employee.block, block2)
        self.assertEqual(employee.department, department2)


class EmployeeAPITest(TestCase, APITestMixin):
    """Test cases for Employee API endpoints"""

    def setUp(self):
        """Set up test data"""
        from apps.core.models import AdministrativeUnit, Province

        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # Create test organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )
        self.department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=self.branch,
            block=self.block,
        )

        # Create test employees
        self.employee1 = Employee.objects.create(
            fullname="John Doe",
            username="emp001",
            email="emp1@example.com",
            phone="1234567890",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        self.employee2 = Employee.objects.create(
            fullname="Jane Smith",
            username="emp002",
            email="emp2@example.com",
            phone="2234567890",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        self.employee3 = Employee.objects.create(
            fullname="Bob Johnson",
            username="emp003",
            email="emp3@example.com",
            phone="3234567890",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

    def test_list_employees(self):
        """Test listing all employees"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 3)
        self.assertEqual(len(results), 3)
        codes = {item["code"] for item in results}
        self.assertTrue(all(code.startswith("MV") for code in codes))

    def test_filter_employees_by_code(self):
        """Test filtering employees by code"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"code": self.employee1.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 1)
        self.assertEqual(results[0]["code"], self.employee1.code)

    def test_filter_employees_by_fullname(self):
        """Test filtering employees by fullname"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"fullname": "John"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(any("John" in item["fullname"] for item in results))

    def test_search_employees(self):
        """Test searching employees"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "Jane"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(any(item["fullname"] == "Jane Smith" for item in results))

    def test_list_employees_pagination(self):
        """Test employee list pagination"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"page": 1, "page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 2)
        self.assertLessEqual(len(results), 2)

    def test_retrieve_employee(self):
        """Test retrieving a single employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["fullname"], "John Doe")
        self.assertEqual(data["username"], "emp001")
        self.assertEqual(data["email"], "emp1@example.com")
        self.assertIn("user", data)
        self.assertIn("branch", data)
        self.assertIn("block", data)
        self.assertIn("department", data)

    def test_create_employee(self):
        """Test creating an employee"""
        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Alice Williams",
            "username": "emp004",
            "email": "emp4@example.com",
            "phone": "4234567890",
            "department_id": self.department.id,
            "note": "Test note",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertTrue(data["code"].startswith("MV"))
        self.assertEqual(data["fullname"], "Alice Williams")
        self.assertEqual(data["username"], "emp004")
        self.assertEqual(data["email"], "emp4@example.com")
        self.assertTrue(Employee.objects.filter(username="emp004").exists())

        # Verify user was created
        employee = Employee.objects.get(username="emp004")
        self.assertIsNotNone(employee.user)
        self.assertEqual(employee.user.username, "emp004")
        # Verify branch and block were auto-set from department
        self.assertEqual(employee.branch, self.branch)
        self.assertEqual(employee.block, self.block)

    def test_update_employee(self):
        """Test updating an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {
            "fullname": "John Updated",
            "username": "emp001",
            "email": "emp1@example.com",
            "phone": "9999999999",
            "department_id": self.department.id,
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["fullname"], "John Updated")
        self.assertEqual(data["phone"], "9999999999")

        self.employee1.refresh_from_db()
        self.assertEqual(self.employee1.fullname, "John Updated")
        self.assertEqual(self.employee1.phone, "9999999999")

    def test_partial_update_employee(self):
        """Test partially updating an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {"fullname": "John Partially Updated"}
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["fullname"], "John Partially Updated")

        self.employee1.refresh_from_db()
        self.assertEqual(self.employee1.fullname, "John Partially Updated")

    def test_delete_employee(self):
        """Test deleting an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee3.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Employee.objects.filter(id=self.employee3.id).exists())

    def test_create_employee_invalid_block(self):
        """Test that branch and block are auto-set from department"""
        # Create a second branch with its own block and department
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=branch2,
            block_type=Block.BlockType.BUSINESS,
        )
        department2 = Department.objects.create(
            code="PB002",
            name="Test Department 2",
            branch=branch2,
            block=block2,
        )

        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Test Employee",
            "username": "testuser",
            "email": "testuser@example.com",
            "department_id": department2.id,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)

        # Verify that branch and block were auto-set from department2
        employee = Employee.objects.get(username="testuser")
        self.assertEqual(employee.branch, branch2)
        self.assertEqual(employee.block, block2)
        self.assertEqual(employee.department, department2)
