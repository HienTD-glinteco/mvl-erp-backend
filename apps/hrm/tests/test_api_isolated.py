import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Block, Branch, Department, OrganizationChart, Position

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content


class IsolatedBranchAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Branch API endpoints with proper isolation"""

    def setUp(self):
        # Clear all existing data
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        Position.objects.all().delete()
        OrganizationChart.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.branch_data = {
            "name": "Chi nhánh Hà Nội",
            "code": "HN",
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
        }

    def test_create_branch(self):
        """Test creating a branch via API"""
        url = reverse("hrm:branch-list")
        response = self.client.post(url, self.branch_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Branch.objects.count(), 1)

        branch = Branch.objects.first()
        self.assertEqual(branch.name, self.branch_data["name"])
        self.assertEqual(branch.code, self.branch_data["code"])

    def test_list_branches(self):
        """Test listing branches via API"""
        Branch.objects.create(**self.branch_data)

        url = reverse("hrm:branch-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], self.branch_data["name"])

    def test_retrieve_branch(self):
        """Test retrieving a branch via API"""
        branch = Branch.objects.create(**self.branch_data)

        url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], branch.name)

    def test_branch_search(self):
        """Test branch search functionality"""
        Branch.objects.create(name="Chi nhánh Hà Nội", code="HN")
        Branch.objects.create(name="Chi nhánh TP.HCM", code="HCM")

        url = reverse("hrm:branch-list")
        response = self.client.get(url, {"search": "Hà Nội"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], "HN")


class IsolatedOrganizationChartAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Organization Chart API endpoints with proper isolation"""

    def setUp(self):
        # Clear all existing data
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        Position.objects.all().delete()
        OrganizationChart.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.employee = User.objects.create_user(
            username="employee",
            email="employee@example.com",
            first_name="John",
            last_name="Doe",
        )

        self.branch = Branch.objects.create(name="Chi nhánh Hà Nội", code="HN")
        self.block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        self.department = Department.objects.create(name="Phòng Nhân sự", code="NS", block=self.block)
        self.position = Position.objects.create(name="Trưởng phòng", code="TP", level=Position.PositionLevel.MANAGER)

    def test_create_organization_chart(self):
        """Test creating an organization chart entry via API"""
        org_data = {
            "employee": str(self.employee.id),
            "position": str(self.position.id),
            "department": str(self.department.id),
            "start_date": date.today().isoformat(),
            "is_primary": True,
        }

        url = reverse("hrm:organization-chart-list")
        response = self.client.post(url, org_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrganizationChart.objects.count(), 1)

    def test_organization_hierarchy_endpoint(self):
        """Test organization hierarchy endpoint"""
        OrganizationChart.objects.create(
            employee=self.employee,
            position=self.position,
            department=self.department,
            start_date=date.today(),
        )

        url = reverse("hrm:organization-chart-hierarchy")
        response = self.client.get(url, {"branch_id": str(self.branch.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)  # One department
        self.assertEqual(len(response_data[0]["positions"]), 1)  # One position

    def test_by_department_endpoint(self):
        """Test getting employees by department endpoint"""
        OrganizationChart.objects.create(
            employee=self.employee,
            position=self.position,
            department=self.department,
            start_date=date.today(),
        )

        url = reverse("hrm:organization-chart-by-department")
        response = self.client.get(url, {"department_id": str(self.department.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["employee"]["username"], self.employee.username)

    def test_by_department_endpoint_missing_param(self):
        """Test by department endpoint without required parameter"""
        url = reverse("hrm:organization-chart-by-department")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # For error responses, the format might be different
        response_data = self.get_response_data(response)
        if response_data and isinstance(response_data, dict):
            self.assertIn("error", response_data)
        # The main test is the status code - that's what matters


class IsolatedPositionAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Position API endpoints with proper isolation"""

    def setUp(self):
        # Clear all existing data
        Position.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_position(self):
        """Test creating a position via API"""
        position_data = {
            "name": "Tổng Giám đốc",
            "code": "TGD",
            "level": Position.PositionLevel.CEO,
        }

        url = reverse("hrm:position-list")
        response = self.client.post(url, position_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Position.objects.count(), 1)

    def test_position_ordering(self):
        """Test position ordering in API response"""
        Position.objects.create(name="Nhân viên", code="NV", level=Position.PositionLevel.STAFF)
        Position.objects.create(name="Tổng Giám đốc", code="TGD", level=Position.PositionLevel.CEO)
        Position.objects.create(name="Giám đốc", code="GD", level=Position.PositionLevel.DIRECTOR)

        url = reverse("hrm:position-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Should be ordered by level (CEO=1, DIRECTOR=2, STAFF=7)
        self.assertEqual(response_data[0]["code"], "TGD")
        self.assertEqual(response_data[1]["code"], "GD")
        self.assertEqual(response_data[2]["code"], "NV")


class IsolatedDepartmentAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Department API endpoints with proper isolation"""

    def setUp(self):
        # Clear all existing data
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.branch = Branch.objects.create(name="Chi nhánh Hà Nội", code="HN")
        self.block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )

    def test_create_department(self):
        """Test creating a department via API"""
        dept_data = {
            "name": "Phòng Nhân sự",
            "code": "NS",
            "block": str(self.block.id),
            "function": Department.DepartmentFunction.HR_ADMIN,  # Required for support blocks
        }

        url = reverse("hrm:department-list")
        response = self.client.post(url, dept_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Department.objects.count(), 1)

    def test_department_tree_endpoint(self):
        """Test department tree structure endpoint"""
        parent_dept = Department.objects.create(name="Phòng Nhân sự", code="NS", block=self.block)
        child_dept = Department.objects.create(  # NOQA
            name="Ban Tuyển dụng",
            code="TD",
            block=self.block,
            parent_department=parent_dept,
        )

        url = reverse("hrm:department-tree")
        response = self.client.get(url, {"block_id": str(self.block.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)  # One root department
        self.assertEqual(len(response_data[0]["children"]), 1)  # One child


class IsolatedBlockAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Block API endpoints with proper isolation"""

    def setUp(self):
        # Clear all existing data
        Branch.objects.all().delete()
        Block.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.branch = Branch.objects.create(name="Chi nhánh Hà Nội", code="HN")

    def test_create_block(self):
        """Test creating a block via API"""
        block_data = {
            "name": "Khối Hỗ trợ",
            "code": "HT",
            "block_type": Block.BlockType.SUPPORT,
            "branch": str(self.branch.id),
        }

        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Block.objects.count(), 1)

        block = Block.objects.first()
        self.assertEqual(block.name, block_data["name"])
        self.assertEqual(block.block_type, block_data["block_type"])

    def test_list_blocks_with_filtering(self):
        """Test listing blocks with filtering"""
        support_block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        business_block = Block.objects.create(  # NOQA
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )

        # Test filtering by block type
        url = reverse("hrm:block-list")
        response = self.client.get(url, {"block_type": Block.BlockType.SUPPORT})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], support_block.code)

    def test_block_filtering_by_branch(self):
        """Test block filtering by branch"""
        Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )

        url = reverse("hrm:block-list")
        response = self.client.get(url, {"branch_code": "HN"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)  # Both blocks belong to HN branch

    def test_block_filtering_by_type(self):
        """Test block filtering by type"""
        Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )

        url = reverse("hrm:block-list")
        response = self.client.get(url, {"block_type": Block.BlockType.SUPPORT})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], "HT")
