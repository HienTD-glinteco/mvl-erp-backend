import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.core.models import Role
from apps.hrm.models import Employee

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
class TestEmployeeRoleAPI(APITestMixin):
    """Test cases for Employee Role Management API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser

    @pytest.fixture
    def roles(self):
        """Create roles for testing"""
        manager = Role.objects.create(name="Manager", code="VT003", description="Manager role")
        staff = Role.objects.create(name="Staff", code="VT004", description="Staff role")
        return manager, staff

    @pytest.fixture
    def setup_employees(self, roles, branch, block, department, position):
        """Create test employees and corresponding user records"""
        role_manager, role_staff = roles

        # Create test users
        u1 = User.objects.create_superuser(
            username="NV001",
            email="emp1@example.com",
            password="testpass123",
            first_name="Nguyễn",
            last_name="Văn A",
            role=role_staff,
        )

        u2 = User.objects.create_superuser(
            username="NV002",
            email="emp2@example.com",
            password="testpass123",
            first_name="Trần",
            last_name="Thị B",
            role=role_staff,
        )

        u3 = User.objects.create_superuser(
            username="NV003",
            email="emp3@example.com",
            password="testpass123",
            first_name="Lê",
            last_name="Văn C",
            role=role_manager,
        )

        # Create Employee records
        e1 = Employee.objects.create(
            code="NV001",
            fullname="Nguyễn Văn A",
            username="emp1",
            email="emp1_hrm@example.com",
            phone="0123456781",
            attendance_code="EMP1",
            date_of_birth="1990-01-01",
            personal_email="emp1.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            user=u1,
            citizen_id="000000020022",
        )

        e2 = Employee.objects.create(
            code="NV002",
            fullname="Trần Thị B",
            username="emp2",
            email="emp2_hrm@example.com",
            phone="0123456782",
            attendance_code="EMP2",
            date_of_birth="1990-01-01",
            personal_email="emp2.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            user=u2,
            citizen_id="000000020023",
        )

        e3 = Employee.objects.create(
            code="NV003",
            fullname="Lê Văn C",
            username="emp3",
            email="emp3_hrm@example.com",
            phone="0123456783",
            attendance_code="EMP3",
            date_of_birth="1990-01-01",
            personal_email="emp3.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            user=u3,
            citizen_id="000000020024",
        )

        return (u1, u2, u3), (e1, e2, e3)

    def test_list_employee_roles(self, setup_employees):
        """Test QTNV 3.2.1.1 - Xem danh sách Nhân viên theo Role"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Should have 3 employees
        assert len(response_data) == 3

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
            assert field in first_employee

    def test_filter_employee_roles_by_invalid_branch_returns_empty(self, setup_employees):
        """Filtering employee roles by a non-existent branch should return an empty list."""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"branch": 999999})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 0

    def test_list_employee_roles_ordering(self, setup_employees):
        """Test QTNV 3.2.1.1 - Sắp xếp giảm dần theo Mã Nhân viên"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Default ordering should be descending by employee code (username)
        # NV003, NV002, NV001
        assert response_data[0]["employee_code"] == "NV003"
        assert response_data[1]["employee_code"] == "NV002"
        assert response_data[2]["employee_code"] == "NV001"

    def test_search_by_employee_name(self, setup_employees):
        """Test QTNV 3.2.1.2 - Tìm kiếm Nhân viên theo Tên"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"search": "Nguyễn"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Should find employee1 (Nguyễn Văn A)
        assert len(response_data) == 1
        assert response_data[0]["employee_code"] == "NV001"

    def test_search_by_role_name(self, setup_employees):
        """Test QTNV 3.2.1.2 - Tìm kiếm Nhân viên theo Vai trò"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"search": "Manager"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Should find employee3 (Manager role)
        assert len(response_data) == 1
        assert response_data[0]["employee_code"] == "NV003"

    def test_search_case_insensitive(self, setup_employees):
        """Test QTNV 3.2.1.2 - Không phân biệt chữ hoa/chữ thường"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"search": "manager"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Should find employee3 (Manager role) with case-insensitive search
        assert len(response_data) == 1

    def test_search_by_employee_fullname(self, setup_employees):
        """Test searching employees by fullname from employee record"""
        url = reverse("hrm:employee-role-list")
        # Search for partial match in fullname
        response = self.client.get(url, {"search": "Thị B"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Should find employee2 (Trần Thị B from Employee.fullname)
        assert len(response_data) == 1
        assert response_data[0]["employee_code"] == "NV002"

    def test_filter_by_branch(self, setup_employees, branch):
        """Test QTNV 3.2.1.3 - Lọc theo Chi nhánh"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"branch": branch.id})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # All 3 employees are in this branch
        assert len(response_data) == 3

    def test_filter_by_role(self, setup_employees, roles):
        """Test QTNV 3.2.1.3 - Lọc theo Vai trò"""
        _, role_staff = roles
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"role": role_staff.id})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Should find 2 employees with Staff role
        assert len(response_data) == 2

    def test_filter_by_department(self, setup_employees, department):
        """Test QTNV 3.2.1.3 - Lọc theo Phòng ban"""
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"department": department.id})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # All 3 employees are in this department
        assert len(response_data) == 3

    def test_bulk_update_roles_success(self, setup_employees, roles):
        """Test QTNV 3.2.4 - Chỉnh sửa Role của nhân viên thành công"""
        users, _ = setup_employees
        u1, u2, _ = users
        manager_role, _ = roles
        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {
            "employee_ids": [u1.id, u2.id],
            "new_role_id": manager_role.id,
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()

        assert response_data["success"]
        # Data is wrapped in envelope
        assert response_data["data"]["updated_count"] == 2

        # Verify roles were updated
        u1.refresh_from_db()
        u2.refresh_from_db()
        assert u1.role == manager_role
        assert u2.role == manager_role

    def test_bulk_update_roles_invalidates_sessions(self, setup_employees, roles):
        """Test that bulk update invalidates sessions"""
        users, _ = setup_employees
        u1, u2, _ = users
        manager_role, _ = roles
        # Set active session keys
        u1.active_session_key = "session_key_1"
        u1.save()
        u2.active_session_key = "session_key_2"
        u2.save()

        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {
            "employee_ids": [u1.id, u2.id],
            "new_role_id": manager_role.id,
        }

        response = self.client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Verify sessions were invalidated
        u1.refresh_from_db()
        u2.refresh_from_db()
        assert u1.active_session_key == ""
        assert u2.active_session_key == ""

    def test_bulk_update_roles_no_selection(self, roles):
        """Test QTNV 3.2.4 - Error when no employee selected"""
        manager_role, _ = roles
        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {"employee_ids": [], "new_role_id": manager_role.id}

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_update_roles_too_many_employees(self, roles):
        """Test QTNV 3.2.4 - Error when more than 25 employees selected"""
        manager_role, staff_role = roles
        # Create 26 employees
        employee_ids = []
        for i in range(26):
            emp = User.objects.create_superuser(
                username=f"EMP{i:03d}", email=f"emp{i:03d}@example.com", password="testpass123", role=staff_role
            )
            employee_ids.append(emp.id)

        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {"employee_ids": employee_ids, "new_role_id": manager_role.id}

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_update_roles_no_role_selected(self, setup_employees):
        """Test QTNV 3.2.4 - Error when no role selected"""
        users, _ = setup_employees
        u1, _, _ = users
        url = reverse("hrm:employee-role-bulk-update-roles")
        data = {"employee_ids": [u1.id]}

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_combined_search_and_filter(self, setup_employees, roles):
        """Test combining search with filters"""
        _, staff_role = roles
        url = reverse("hrm:employee-role-list")
        response = self.client.get(url, {"search": "Văn", "role": staff_role.id})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Should find employee1 (Nguyễn Văn A with Staff role)
        assert len(response_data) == 1
        assert response_data[0]["employee_code"] == "NV001"

    def test_search_by_employee_code(self, setup_employees):
        """Test searching employees by employee code (employee__code field)"""
        url = reverse("hrm:employee-role-list")
        # Search for exact employee code
        response = self.client.get(url, {"search": "NV001"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Should find employee1 with code NV001
        assert len(response_data) == 1
        assert response_data[0]["employee_code"] == "NV001"
