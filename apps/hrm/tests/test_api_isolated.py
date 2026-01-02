import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import Block, Branch, Department, Position

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses"""

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
class TestIsolatedBranchAPI(APITestMixin):
    """Test cases for Branch API endpoints with proper isolation"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, province, admin_unit):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser
        self.province = province
        self.administrative_unit = admin_unit

        self.branch_data = {
            "name": "Chi nhánh Hà Nội",
            "code": "HN",
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
            "province_id": self.province.id,
            "administrative_unit_id": self.administrative_unit.id,
        }

    def test_create_branch(self):
        """Test creating a branch via API"""
        url = reverse("hrm:branch-list")
        response = self.client.post(url, self.branch_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Branch.objects.count() == 1

        branch = Branch.objects.first()
        assert branch.name == self.branch_data["name"]
        # Code is now auto-generated, not from provided data
        assert branch.code.startswith("CN")

    def test_list_branches(self):
        """Test listing branches via API"""
        Branch.objects.create(
            name=self.branch_data["name"],
            code=self.branch_data["code"],
            address=self.branch_data.get("address", ""),
            phone=self.branch_data.get("phone", ""),
            email=self.branch_data.get("email", ""),
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        url = reverse("hrm:branch-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == self.branch_data["name"]

    def test_retrieve_branch(self):
        """Test retrieving a branch via API"""
        branch = Branch.objects.create(
            name=self.branch_data["name"],
            code=self.branch_data["code"],
            address=self.branch_data.get("address", ""),
            phone=self.branch_data.get("phone", ""),
            email=self.branch_data.get("email", ""),
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == branch.name

    def test_branch_search(self):
        """Test branch search functionality"""
        Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )
        Branch.objects.create(
            name="Chi nhánh TP.HCM",
            code="HCM",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        url = reverse("hrm:branch-list")
        response = self.client.get(url, {"search": "Hà Nội"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == "HN"


# IsolatedOrganizationChartAPITest class removed - OrganizationChart API no longer exists
@pytest.mark.django_db
class TestIsolatedPositionAPI(APITestMixin):
    """Test cases for Position API endpoints with proper isolation"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser

    def test_create_position(self):
        """Test creating a position via API"""
        position_data = {
            "name": "Tổng Giám đốc",
            "code": "TGD",
        }

        url = reverse("hrm:position-list")
        response = self.client.post(url, position_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Position.objects.count() == 1

    def test_position_ordering(self):
        """Test position ordering in API response"""
        Position.objects.create(name="Nhân viên", code="NV")
        Position.objects.create(name="Tổng Giám đốc", code="TGD")
        Position.objects.create(name="Giám đốc", code="GD")

        url = reverse("hrm:position-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # Should be ordered by name alphabetically (Giám đốc, Nhân viên, Tổng Giám đốc)
        assert response_data[0]["code"] == "GD"
        assert response_data[1]["code"] == "NV"
        assert response_data[2]["code"] == "TGD"


@pytest.mark.django_db
class TestIsolatedDepartmentAPI(APITestMixin):
    """Test cases for Department API endpoints with proper isolation"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, branch, block):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser
        self.branch = branch
        self.block = block
        # Ensure block is SUPPORT type for department creation test
        self.block.block_type = Block.BlockType.SUPPORT
        self.block.save()

    def test_create_department(self):
        """Test creating a department via API"""
        dept_data = {
            "name": "Phòng Nhân sự",
            "branch_id": str(self.branch.id),
            "block_id": str(self.block.id),
            "function": Department.DepartmentFunction.HR_ADMIN,  # Required for support blocks
        }

        url = reverse("hrm:department-list")
        response = self.client.post(url, dept_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Department.objects.count() == 1

    def test_department_tree_endpoint(self):
        """Test department tree structure endpoint"""
        parent_dept = Department.objects.create(name="Phòng Nhân sự", branch=self.branch, block=self.block)
        child_dept = Department.objects.create(  # NOQA
            name="Ban Tuyển dụng",
            branch=self.branch,
            block=self.block,
            parent_department=parent_dept,
        )

        url = reverse("hrm:department-tree")
        response = self.client.get(url, {"block_id": str(self.block.id)})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1  # One root department
        assert len(response_data[0]["children"]) == 1  # One child


@pytest.mark.django_db
class TestIsolatedBlockAPI(APITestMixin):
    """Test cases for Block API endpoints with proper isolation"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, branch):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser
        self.branch = branch

    def test_create_block(self):
        """Test creating a block via API"""
        block_data = {
            "name": "Khối Hỗ trợ",
            "code": "HT",
            "block_type": Block.BlockType.SUPPORT,
            "branch_id": str(self.branch.id),
        }

        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Block.objects.count() == 1

        block = Block.objects.first()
        assert block.name == block_data["name"]
        assert block.block_type == block_data["block_type"]

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

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == support_block.code

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
        response = self.client.get(url, {"branch_code": self.branch.code})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2  # Both blocks belong to this branch

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

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == "HT"
