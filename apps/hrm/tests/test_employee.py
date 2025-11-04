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
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010000",
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
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010001",
        )

        # Cannot create with same code manually
        with self.assertRaises(Exception):
            Employee.objects.create(
                code=employee1.code,
                fullname="Jane Doe",
                username="janedoe",
                email="jane@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=self.branch,
                block=self.block,
                department=self.department,
                citizen_id="000000010002",
            )

    def test_employee_username_unique(self):
        """Test that username must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010003",
        )

        with self.assertRaises(Exception):
            Employee.objects.create(
                fullname="Jane Doe",
                username="johndoe",
                email="jane@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=self.branch,
                block=self.block,
                department=self.department,
                citizen_id="000000010004",
            )

    def test_employee_email_unique(self):
        """Test that email must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010005",
        )

        with self.assertRaises(Exception):
            Employee.objects.create(
                fullname="Jane Doe",
                username="janedoe",
                email="john@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=self.branch,
                block=self.block,
                department=self.department,
                citizen_id="000000010006",
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
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch2,
            block=self.block,  # This block belongs to self.branch, not branch2
            department=self.department,
        )

        employee.save()
        self.assertNotEqual(employee.branch, branch2)
        self.assertEqual(employee.branch, self.department.branch)

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
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=block2,
            department=self.department,  # This department belongs to self.block, not block2
        )

        employee.save()
        self.assertNotEqual(employee.block, block2)
        self.assertEqual(employee.block, self.department.block)

    def test_employee_auto_assign_branch_block_from_department(self):
        """Test that branch and block are auto-assigned from department on save"""
        # Create employee with only department specified
        employee = Employee.objects.create(
            fullname="Auto Assign Test",
            username="autotest",
            email="autotest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="autotest.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="000000010007",
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
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="transfertest.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="000000010008",
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

    def test_employee_resignation_validation_requires_date(self):
        """Test that resignation_date is required when status is Resigned"""
        from django.core.exceptions import ValidationError

        employee = Employee(
            fullname="Resigned Employee",
            username="resignedtest",
            email="resignedtest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="resigned.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.CAREER_CHANGE,
        )

        with self.assertRaises(ValidationError) as context:
            employee.save()

        self.assertIn("resignation_date", context.exception.message_dict)

    def test_employee_resignation_validation_requires_reason(self):
        """Test that resignation_reason is required when status is Resigned"""
        from django.core.exceptions import ValidationError

        employee = Employee(
            fullname="Resigned Employee",
            username="resignedtest",
            email="resignedtest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="resigned.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            status=Employee.Status.RESIGNED,
            resignation_date="2024-12-31",
        )

        with self.assertRaises(ValidationError) as context:
            employee.save()

        self.assertIn("resignation_reason", context.exception.message_dict)

    def test_employee_resignation_validation_both_fields_required(self):
        """Test that both resignation_date and resignation_reason are required when status is Resigned"""
        from django.core.exceptions import ValidationError

        employee = Employee(
            fullname="Resigned Employee",
            username="resignedtest",
            email="resignedtest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="resigned.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            status=Employee.Status.RESIGNED,
        )

        with self.assertRaises(ValidationError) as context:
            employee.save()

        self.assertIn("resignation_date", context.exception.message_dict)

    def test_employee_resignation_valid(self):
        """Test that employee with Resigned status and both fields is valid"""
        employee = Employee.objects.create(
            fullname="Resigned Employee",
            username="resignedtest",
            email="resignedtest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="resigned.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            status=Employee.Status.RESIGNED,
            resignation_date="2024-12-31",
            resignation_reason=Employee.ResignationReason.CAREER_CHANGE,
            citizen_id="000000010009",
        )

        self.assertEqual(employee.status, Employee.Status.RESIGNED)
        self.assertEqual(employee.resignation_date, "2024-12-31")
        self.assertEqual(employee.resignation_reason, Employee.ResignationReason.CAREER_CHANGE)

    def test_employee_colored_code_type_property(self):
        """Test that colored_code_type property returns correct format"""
        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testcolor",
            email="testcolor@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testcolor.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            code_type=Employee.CodeType.MV,
            citizen_id="000000010010",
        )

        colored_value = employee.colored_code_type
        self.assertIsNotNone(colored_value)
        self.assertIn("value", colored_value)
        self.assertIn("variant", colored_value)
        self.assertEqual(colored_value["value"], "MV")

    def test_employee_colored_status_property(self):
        """Test that colored_status property returns correct format"""
        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testcolor",
            email="testcolor@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testcolor.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            status=Employee.Status.ACTIVE,
            citizen_id="000000010011",
        )

        colored_value = employee.colored_status
        self.assertIsNotNone(colored_value)
        self.assertIn("value", colored_value)
        self.assertIn("variant", colored_value)
        self.assertEqual(colored_value["value"], "Active")


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
            attendance_code="EMP001",
            date_of_birth="1990-01-01",
            personal_email="emp1.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010012",
        )

        self.employee2 = Employee.objects.create(
            fullname="Jane Smith",
            username="emp002",
            email="emp2@example.com",
            phone="2234567890",
            attendance_code="EMP002",
            date_of_birth="1991-01-01",
            personal_email="emp2.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010013",
        )

        self.employee3 = Employee.objects.create(
            fullname="Bob Johnson",
            username="emp003",
            email="emp3@example.com",
            phone="3234567890",
            attendance_code="EMP003",
            date_of_birth="1992-01-01",
            personal_email="emp3.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010014",
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
            "attendance_code": "58607083146091314660",
            "date_of_birth": "1993-01-01",
            "personal_email": "emp4.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "note": "Test note",
            "citizen_id": "665030149161",
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
            "attendance_code": "586070831460",
            "date_of_birth": "1990-01-01",
            "personal_email": "emp1.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "citizen_id": "104085808593",
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
            "phone": "5555555555",
            "attendance_code": "586070831460",
            "date_of_birth": "1994-01-01",
            "personal_email": "testuser.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": department2.id,
            "citizen_id": "608498989398",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)

        # Verify that branch and block were auto-set from department2
        employee = Employee.objects.get(username="testuser")
        self.assertEqual(employee.branch, branch2)
        self.assertEqual(employee.block, block2)
        self.assertEqual(employee.department, department2)

    def test_create_employee_resigned_without_date_fails(self):
        """Test that creating employee with Resigned status without resignation_date fails"""
        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Resigned Employee",
            "username": "resigned001",
            "email": "resigned001@example.com",
            "phone": "5555555555",
            "attendance_code": "586070831460",
            "date_of_birth": "1994-01-01",
            "personal_email": "resigned001.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "status": "Resigned",
            "resignation_reason": "Career Change",
            "citizen_id": "944477823080",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_create_employee_resigned_without_reason_fails(self):
        """Test that creating employee with Resigned status without resignation_reason fails"""
        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Resigned Employee",
            "username": "resigned001",
            "email": "resigned001@example.com",
            "phone": "5555555555",
            "attendance_code": "586070831460",
            "date_of_birth": "1994-01-01",
            "personal_email": "resigned001.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "status": "Resigned",
            "resignation_date": "2024-12-31",
            "citizen_id": "666814324396",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_create_employee_resigned_with_both_fields_succeeds(self):
        """Test that creating employee with Resigned status with both fields succeeds"""
        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Resigned Employee",
            "username": "resigned001",
            "email": "resigned001@example.com",
            "phone": "5555555555",
            "attendance_code": "586070831460",
            "date_of_birth": "1994-01-01",
            "personal_email": "resigned001.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "status": "Resigned",
            "resignation_date": "2024-12-31",
            "resignation_reason": "Career Change",
            "citizen_id": "632438842613",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        employee = Employee.objects.get(username="resigned001")
        self.assertEqual(employee.status, "Resigned")
        self.assertEqual(employee.resignation_date.isoformat(), "2024-12-31")
        self.assertEqual(employee.resignation_reason, "Career Change")

    def test_update_employee_to_resigned_without_fields_fails(self):
        """Test that updating employee status to Resigned without required fields fails"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {
            "fullname": self.employee1.fullname,
            "username": self.employee1.username,
            "email": self.employee1.email,
            "phone": self.employee1.phone,
            "attendance_code": self.employee1.attendance_code,
            "date_of_birth": "1990-01-01",
            "personal_email": self.employee1.personal_email,
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "status": "Resigned",
            "citizen_id": "363379597750",
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_retrieve_employee_includes_colored_values(self):
        """Test that retrieving employee includes colored_code_type and colored_status"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check colored_code_type
        self.assertIn("colored_code_type", data)
        self.assertIsNotNone(data["colored_code_type"])
        self.assertIn("value", data["colored_code_type"])
        self.assertIn("variant", data["colored_code_type"])

        # Check colored_status
        self.assertIn("colored_status", data)
        self.assertIsNotNone(data["colored_status"])
        self.assertIn("value", data["colored_status"])
        self.assertIn("variant", data["colored_status"])

    def test_list_employees_includes_colored_values(self):
        """Test that listing employees includes colored values"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertGreater(count, 0)
        for item in results:
            self.assertIn("colored_code_type", item)
            self.assertIn("colored_status", item)

    def test_create_employee_with_position_and_contract_type(self):
        """Test creating employee with optional position_id and contract_type_id"""
        from apps.hrm.models import ContractType, Position

        position = Position.objects.create(code="POS001", name="Test Position")
        contract_type = ContractType.objects.create(name="Full-time")

        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Employee With Position",
            "username": "emp_with_pos",
            "email": "emp_with_pos@example.com",
            "phone": "6666666666",
            "attendance_code": "586070831460",
            "date_of_birth": "1995-01-01",
            "personal_email": "emp_with_pos.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "position_id": position.id,
            "contract_type_id": contract_type.id,
            "citizen_id": "446130818974",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)

        # Verify nested objects are returned in response
        self.assertIn("position", data)
        self.assertIsNotNone(data["position"])
        self.assertEqual(data["position"]["id"], position.id)
        self.assertEqual(data["position"]["name"], "Test Position")

        self.assertIn("contract_type", data)
        self.assertIsNotNone(data["contract_type"])
        self.assertEqual(data["contract_type"]["id"], contract_type.id)
        self.assertEqual(data["contract_type"]["name"], "Full-time")

        # Verify in database
        employee = Employee.objects.get(username="emp_with_pos")
        self.assertEqual(employee.position.id, position.id)
        self.assertEqual(employee.contract_type.id, contract_type.id)

    def test_serializer_returns_nested_objects_for_read(self):
        """Test that serializer returns full nested objects for branch, block, department"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Branch should be nested object with id, name, code
        self.assertIn("branch", data)
        self.assertIsInstance(data["branch"], dict)
        self.assertIn("id", data["branch"])
        self.assertIn("name", data["branch"])
        self.assertIn("code", data["branch"])
        self.assertEqual(data["branch"]["id"], self.branch.id)

        # Block should be nested object
        self.assertIn("block", data)
        self.assertIsInstance(data["block"], dict)
        self.assertIn("id", data["block"])
        self.assertIn("name", data["block"])
        self.assertIn("code", data["block"])
        self.assertEqual(data["block"]["id"], self.block.id)

        # Department should be nested object
        self.assertIn("department", data)
        self.assertIsInstance(data["department"], dict)
        self.assertIn("id", data["department"])
        self.assertIn("name", data["department"])
        self.assertIn("code", data["department"])
        self.assertEqual(data["department"]["id"], self.department.id)

        # User should be nested object
        self.assertIn("user", data)
        self.assertIsInstance(data["user"], dict)

    def test_create_employee_without_date_of_birth(self):
        """Test creating an employee without date_of_birth (should be optional now)"""
        employee = Employee.objects.create(
            fullname="Jane Doe",
            username="janedoe",
            email="jane@example.com",
            phone="0123456788",
            attendance_code="12346",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010015",
        )
        self.assertIsNone(employee.date_of_birth)
        self.assertEqual(employee.fullname, "Jane Doe")
        self.assertEqual(employee.email, "jane@example.com")

    def test_create_employee_without_personal_email(self):
        """Test creating an employee without personal_email (should be optional now)"""
        employee = Employee.objects.create(
            fullname="Bob Smith",
            username="bobsmith",
            email="bob@example.com",
            phone="0123456787",
            attendance_code="12347",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010016",
        )
        self.assertIsNone(employee.personal_email)
        self.assertEqual(employee.fullname, "Bob Smith")
        self.assertEqual(employee.email, "bob@example.com")

    def test_create_employee_with_optional_fields(self):
        """Test creating an employee with optional fields"""
        employee = Employee.objects.create(
            fullname="Alice Johnson",
            username="alicejohnson",
            email="alice@example.com",
            phone="0123456786",
            attendance_code="12348",
            date_of_birth="1995-05-15",
            personal_email="alice.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010017",
        )
        self.assertEqual(str(employee.date_of_birth), "1995-05-15")
        self.assertEqual(employee.personal_email, "alice.personal@example.com")
        self.assertEqual(employee.fullname, "Alice Johnson")

    def test_create_multiple_employees_without_personal_email(self):
        """Test creating multiple employees without personal_email (no unique constraint)"""
        employee1 = Employee.objects.create(
            fullname="Charlie Brown",
            username="charliebrown",
            email="charlie@example.com",
            phone="0123456785",
            attendance_code="12349",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010018",
        )

        employee2 = Employee.objects.create(
            fullname="David Green",
            username="davidgreen",
            email="david@example.com",
            phone="0123456784",
            attendance_code="12350",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010019",
        )

        self.assertIsNone(employee1.personal_email)
        self.assertIsNone(employee2.personal_email)
        # Both should have been created successfully
        self.assertEqual(Employee.objects.filter(personal_email__isnull=True).count(), 2)

    def test_is_onboarding_email_sent_default(self):
        """Test that is_onboarding_email_sent defaults to False"""
        employee = Employee.objects.create(
            fullname="Emily White",
            username="emilywhite",
            email="emily@example.com",
            phone="0123456783",
            attendance_code="12351",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010020",
        )
        self.assertFalse(employee.is_onboarding_email_sent)

    def test_is_onboarding_email_sent_can_be_updated(self):
        """Test that is_onboarding_email_sent can be updated"""
        employee = Employee.objects.create(
            fullname="Frank Black",
            username="frankblack",
            email="frank@example.com",
            phone="0123456782",
            attendance_code="12352",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010021",
        )
        self.assertFalse(employee.is_onboarding_email_sent)

        # Update the field
        employee.is_onboarding_email_sent = True
        employee.save()

        # Verify the update persisted
        employee.refresh_from_db()
        self.assertTrue(employee.is_onboarding_email_sent)


class EmployeeFilterTest(TestCase, APITestMixin):
    """Test cases for Employee API filters"""

    def setUp(self):
        """Set up test data"""
        from datetime import date

        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Position

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

        # Create positions with different is_leadership values
        self.leadership_position = Position.objects.create(
            name="Manager",
            code="MGR",
            is_leadership=True,
        )
        self.regular_position = Position.objects.create(
            name="Staff",
            code="STF",
            is_leadership=False,
        )

        # Create employees with different positions and attributes
        self.leader_employee = Employee.objects.create(
            fullname="Leader One",
            username="leader001",
            email="leader1@example.com",
            phone="1111111111",
            attendance_code="LDR001",
            date_of_birth=date(1985, 3, 15),
            start_date=date(2020, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.leadership_position,
            is_onboarding_email_sent=True,
            citizen_id="000000010022",
        )

        self.staff_employee = Employee.objects.create(
            fullname="Staff One",
            username="staff001",
            email="staff1@example.com",
            phone="2222222222",
            attendance_code="STF001",
            date_of_birth=date(1990, 3, 20),
            start_date=date(2021, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.regular_position,
            is_onboarding_email_sent=False,
            citizen_id="000000010023",
        )

        self.onboarding_employee = Employee.objects.create(
            fullname="Onboarding Employee",
            username="onboarding001",
            email="onboarding1@example.com",
            phone="3333333333",
            attendance_code="ONB001",
            date_of_birth=date(1992, 6, 10),
            start_date=date(2024, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.regular_position,
            is_onboarding_email_sent=True,
            citizen_id="000000010024",
        )

        self.march_birthday_employee = Employee.objects.create(
            fullname="March Birthday",
            username="march001",
            email="march1@example.com",
            phone="4444444444",
            attendance_code="MAR001",
            date_of_birth=date(1988, 3, 5),
            start_date=date(2019, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.leadership_position,
            is_onboarding_email_sent=False,
            citizen_id="000000010025",
        )

    def test_filter_by_position_is_leadership_true(self):
        """Test filtering employees by leadership positions"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 2)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)

    def test_filter_by_position_is_leadership_false(self):
        """Test filtering employees by non-leadership positions"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 2)
        codes = {item["code"] for item in results}
        self.assertIn(self.staff_employee.code, codes)
        self.assertIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.leader_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    def test_filter_by_is_onboarding_email_sent_true(self):
        """Test filtering employees who received onboarding email"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_onboarding_email_sent": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 2)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    def test_filter_by_is_onboarding_email_sent_false(self):
        """Test filtering employees who did not receive onboarding email"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_onboarding_email_sent": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 2)
        codes = {item["code"] for item in results}
        self.assertIn(self.staff_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertNotIn(self.leader_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)

    def test_filter_by_date_of_birth_month_march(self):
        """Test filtering employees born in March (month 3)"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"date_of_birth__month": "3"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 3)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.staff_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)

    def test_filter_by_date_of_birth_month_june(self):
        """Test filtering employees born in June (month 6)"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"date_of_birth__month": "6"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 1)
        codes = {item["code"] for item in results}
        self.assertIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.leader_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    def test_combined_filter_leadership_and_onboarding(self):
        """Test combining leadership and onboarding email filters"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true", "is_onboarding_email_sent": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 1)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    def test_combined_filter_leadership_and_birth_month(self):
        """Test combining leadership and birth month filters"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true", "date_of_birth__month": "3"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 2)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)
