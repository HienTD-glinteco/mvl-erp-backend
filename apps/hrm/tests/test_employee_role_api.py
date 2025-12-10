import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province, Role
from apps.hrm.models import Block, Branch, Department, Employee, Position

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


class EmployeeRoleAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Employee Role Management API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        Position.objects.all().delete()
        User.objects.all().delete()
        Role.objects.all().delete()

        # Create test user for authentication
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # Create roles
        self.role_manager = Role.objects.create(name="Manager", code="VT003", description="Manager role")
        self.role_staff = Role.objects.create(name="Staff", code="VT004", description="Staff role")

        # Create Province and AdministrativeUnit for Branch
        self.province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        # Create organizational structure
        self.branch = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            address="123 Lê Duẩn, Hà Nội",
            phone="0243456789",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.block = Block.objects.create(
            name="Khối Kinh doanh", code="KD", block_type=Block.BlockType.BUSINESS, branch=self.branch
        )

        self.department = Department.objects.create(
            name="Phòng Kinh doanh 1",
            code="KD1",
            block=self.block,
            branch=self.branch,
            function=Department.DepartmentFunction.BUSINESS,
        )

        self.position = Position.objects.create(name="Nhân viên Kinh doanh", code="NVKD")

        # Create test employees
        self.employee1 = User.objects.create_superuser(
            username="NV001",
            email="emp1@example.com",
            password="testpass123",
            first_name="Nguyễn",
            last_name="Văn A",
            role=self.role_staff,
        )

        self.employee2 = User.objects.create_superuser(
            username="NV002",
            email="emp2@example.com",
            password="testpass123",
            first_name="Trần",
            last_name="Thị B",
            role=self.role_staff,
        )

        self.employee3 = User.objects.create_superuser(
            username="NV003",
            email="emp3@example.com",
            password="testpass123",
            first_name="Lê",
            last_name="Văn C",
            role=self.role_manager,
        )

        # Create Employee records for each user with positions
        Employee.objects.create(
            code="NV001",
            fullname="Nguyễn Văn A",
            username="emp1",
            email="emp1_hrm@example.com",
            phone="0123456781",
            attendance_code="EMP1",
            date_of_birth="1990-01-01",
            personal_email="emp1.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            user=self.employee1,
            citizen_id="000000020022",
        )

        Employee.objects.create(
            code="NV002",
            fullname="Trần Thị B",
            username="emp2",
            email="emp2_hrm@example.com",
            phone="0123456782",
            attendance_code="EMP2",
            date_of_birth="1990-01-01",
            personal_email="emp2.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            user=self.employee2,
            citizen_id="000000020023",
        )

        Employee.objects.create(
            code="NV003",
            fullname="Lê Văn C",
            username="emp3",
            email="emp3_hrm@example.com",
            phone="0123456783",
            attendance_code="EMP3",
            date_of_birth="1990-01-01",
            personal_email="emp3.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            user=self.employee3,
            citizen_id="000000020024",
        )

    def test_list_employee_roles(self):
        """Test QTNV 3.2.1.1 - Xem danh sách Nhân viên theo Role"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Should have 3 employees
        self.assertEqual(len(response_data), 3)

        # Check that all required fields are present
        first_employee = response_data[0]
        required_fields = [
            "id",
            "employee_code",
            "employee_name",
            "branch_name",
            "block_name",
            "department_name",
            "position_name",
            "role",
            "role_name",
        ]
        for field in required_fields:
            self.assertIn(field, first_employee)

    def test_filter_employee_roles_by_invalid_branch_returns_empty(self):
        """Filtering employee roles by a non-existent branch should return an empty list."""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"branch": 999999})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 0)

    def test_list_employee_roles_ordering(self):
        """Test QTNV 3.2.1.1 - Sắp xếp giảm dần theo Mã Nhân viên"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Default ordering should be descending by employee code (username)
        # NV003, NV002, NV001
        self.assertEqual(response_data[0]["employee_code"], "NV003")
        self.assertEqual(response_data[1]["employee_code"], "NV002")
        self.assertEqual(response_data[2]["employee_code"], "NV001")

    def test_search_by_employee_name(self):
        """Test QTNV 3.2.1.2 - Tìm kiếm Nhân viên theo Tên"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"search": "Nguyễn"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Should find employee1 (Nguyễn Văn A)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["employee_code"], "NV001")

    def test_search_by_role_name(self):
        """Test QTNV 3.2.1.2 - Tìm kiếm Nhân viên theo Vai trò"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"search": "Manager"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Should find employee3 (Manager role)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["employee_code"], "NV003")

    def test_search_case_insensitive(self):
        """Test QTNV 3.2.1.2 - Không phân biệt chữ hoa/chữ thường"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"search": "manager"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Should find employee3 (Manager role) with case-insensitive search
        self.assertEqual(len(response_data), 1)

    def test_search_by_employee_fullname(self):
        """Test searching employees by fullname from employee record"""
        url = reverse("hrm:employee-role-list")
        # Search for partial match in fullname
        response = self.client.get(url, {"search": "Thị B"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Should find employee2 (Trần Thị B from Employee.fullname)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["employee_code"], "NV002")

    def test_filter_by_branch(self):
        """Test QTNV 3.2.1.3 - Lọc theo Chi nhánh"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"branch": self.branch.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # All 3 employees are in this branch
        self.assertEqual(len(response_data), 3)

    def test_filter_by_role(self):
        """Test QTNV 3.2.1.3 - Lọc theo Vai trò"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"role": self.role_staff.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Should find 2 employees with Staff role
        self.assertEqual(len(response_data), 2)

    def test_filter_by_department(self):
        """Test QTNV 3.2.1.3 - Lọc theo Phòng ban"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"department": self.department.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # All 3 employees are in this department
        self.assertEqual(len(response_data), 3)

    def test_bulk_update_roles_success(self):
        """Test QTNV 3.2.4 - Chỉnh sửa Role của nhân viên thành công"""
        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {
            "employee_ids": [self.employee1.id, self.employee2.id],
            "new_role_id": self.role_manager.id,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        self.assertTrue(response_data["success"])
        # Data is wrapped in envelope
        self.assertEqual(response_data["data"]["updated_count"], 2)

        # Verify roles were updated
        self.employee1.refresh_from_db()
        self.employee2.refresh_from_db()
        self.assertEqual(self.employee1.role, self.role_manager)
        self.assertEqual(self.employee2.role, self.role_manager)

    def test_bulk_update_roles_invalidates_sessions(self):
        """Test that bulk update invalidates sessions"""
        # Set active session keys
        self.employee1.active_session_key = "session_key_1"
        self.employee1.save()
        self.employee2.active_session_key = "session_key_2"
        self.employee2.save()

        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {
            "employee_ids": [self.employee1.id, self.employee2.id],
            "new_role_id": self.role_manager.id,
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify sessions were invalidated
        self.employee1.refresh_from_db()
        self.employee2.refresh_from_db()
        self.assertEqual(self.employee1.active_session_key, "")
        self.assertEqual(self.employee2.active_session_key, "")

    def test_bulk_update_roles_no_selection(self):
        """Test QTNV 3.2.4 - Error when no employee selected"""
        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {"employee_ids": [], "new_role_id": self.role_manager.id}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_update_roles_too_many_employees(self):
        """Test QTNV 3.2.4 - Error when more than 25 employees selected"""
        # Create 26 employees
        employee_ids = []
        for i in range(26):
            emp = User.objects.create_superuser(
                username=f"EMP{i:03d}", email=f"emp{i:03d}@example.com", password="testpass123", role=self.role_staff
            )
            employee_ids.append(emp.id)

        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {"employee_ids": employee_ids, "new_role_id": self.role_manager.id}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_update_roles_no_role_selected(self):
        """Test QTNV 3.2.4 - Error when no role selected"""
        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {"employee_ids": [self.employee1.id]}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_combined_search_and_filter(self):
        """Test combining search with filters"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"search": "Văn", "role": self.role_staff.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Should find employee1 (Nguyễn Văn A with Staff role)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["employee_code"], "NV001")

    def test_search_by_employee_code(self):
        """Test searching employees by employee code (employee__code field)"""
        url = reverse("hrm:employee-role-list")
        # Search for exact employee code
        response = self.client.get(url, {"search": "NV001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Should find employee1 with code NV001
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["employee_code"], "NV001")
