import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, BranchContactInfo, Department, Position

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestBranchAPI(APITestMixin):
    """Test cases for Branch API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def branch_data(self, province, admin_unit):
        return {
            "name": "Chi nhánh Hà Nội",
            "code": "HN",
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
            "province_id": province.id,
            "administrative_unit_id": admin_unit.id,
        }

    def test_create_branch(self, branch_data):
        """Test creating a branch via API"""
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Branch.objects.count() == 1

        branch = Branch.objects.first()
        assert branch.name == branch_data["name"]
        # Code is now auto-generated, not from provided data
        assert branch.code.startswith("CN")

    def test_list_branches(self, branch_data, province, admin_unit):
        """Test listing branches via API"""
        Branch.objects.create(
            name=branch_data["name"],
            code=branch_data["code"],
            address=branch_data["address"],
            phone=branch_data["phone"],
            email=branch_data["email"],
            province=province,
            administrative_unit=admin_unit,
        )

        url = reverse("hrm:branch-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == branch_data["name"]

    def test_retrieve_branch(self, branch_data, province, admin_unit):
        """Test retrieving a branch via API"""
        branch = Branch.objects.create(
            name=branch_data["name"],
            code=branch_data["code"],
            address=branch_data["address"],
            phone=branch_data["phone"],
            email=branch_data["email"],
            province=province,
            administrative_unit=admin_unit,
        )

        url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == branch.name

    def test_update_branch(self, branch_data, province, admin_unit):
        """Test updating a branch via API"""
        branch = Branch.objects.create(
            name=branch_data["name"],
            code=branch_data["code"],
            address=branch_data["address"],
            phone=branch_data["phone"],
            email=branch_data["email"],
            province=province,
            administrative_unit=admin_unit,
        )

        update_data = {"name": "Chi nhánh Hà Nội Updated"}
        url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        response = self.client.patch(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        branch.refresh_from_db()
        assert branch.name == update_data["name"]

    def test_delete_branch(self, branch_data, province, admin_unit):
        """Test deleting a branch via API"""
        branch = Branch.objects.create(
            name=branch_data["name"],
            code=branch_data["code"],
            address=branch_data["address"],
            phone=branch_data["phone"],
            email=branch_data["email"],
            province=province,
            administrative_unit=admin_unit,
        )

        url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Branch.objects.count() == 0


@pytest.mark.django_db
class TestBranchContactInfoAPI(APITestMixin):
    """Test cases for BranchContactInfo API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def contact_payload(self, branch):
        return {
            "branch_id": str(branch.id),
            "business_line": "Mortgage",
            "name": "Alice Nguyen",
            "phone_number": "0912345678",
            "email": "alice.nguyen@example.com",
        }

    def test_create_branch_contact_info(self, contact_payload):
        url = reverse("hrm:branch-contact-info-list")
        response = self.client.post(url, contact_payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert BranchContactInfo.objects.count() == 1
        contact = BranchContactInfo.objects.first()
        assert contact.name == contact_payload["name"]

    def test_list_branch_contact_info(self, branch):
        BranchContactInfo.objects.create(
            branch=branch,
            business_line="Mortgage",
            name="Alice Nguyen",
            phone_number="0912345678",
            email="alice.nguyen@example.com",
        )

        url = reverse("hrm:branch-contact-info-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["business_line"] == "Mortgage"

    def test_filter_branch_contact_info_by_invalid_branch_returns_empty(self, branch):
        BranchContactInfo.objects.create(
            branch=branch,
            business_line="Mortgage",
            name="Alice Nguyen",
            phone_number="0912345678",
            email="alice.nguyen@example.com",
        )

        url = reverse("hrm:branch-contact-info-list")
        response = self.client.get(url, {"branch": 999999})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 0

    def test_update_branch_contact_info(self, branch):
        contact = BranchContactInfo.objects.create(
            branch=branch,
            business_line="Mortgage",
            name="Alice Nguyen",
            phone_number="0912345678",
            email="alice.nguyen@example.com",
        )

        url = reverse("hrm:branch-contact-info-detail", kwargs={"pk": contact.pk})
        response = self.client.patch(url, {"phone_number": "0999999999"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        contact.refresh_from_db()
        assert contact.phone_number == "0999999999"


@pytest.mark.django_db
class TestBlockAPI(APITestMixin):
    """Test cases for Block API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    def test_create_block(self, branch):
        """Test creating a block via API"""
        block_data = {
            "name": "Khối Hỗ trợ",
            "code": "HT",  # This code should be ignored
            "block_type": Block.BlockType.SUPPORT,
            "branch_id": str(branch.id),
        }

        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Block.objects.count() == 1

        block = Block.objects.first()
        assert block.name == block_data["name"]
        assert block.block_type == block_data["block_type"]
        # Verify auto-generated code (should not be "HT")
        assert block.code != "HT"
        assert block.code.startswith("KH")

    def test_list_blocks_with_filtering(self, branch):
        """Test listing blocks with filtering"""
        support_block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=branch,
        )
        Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=branch,
        )

        # Test filtering by block type
        url = reverse("hrm:block-list")
        response = self.client.get(url, {"block_type": Block.BlockType.SUPPORT})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == support_block.code

    def test_filter_blocks_by_invalid_branch_returns_empty(self, branch):
        Block.objects.create(
            name="Khối Hỗ trợ",
            code="HTX",
            block_type=Block.BlockType.SUPPORT,
            branch=branch,
        )

        url = reverse("hrm:block-list")
        response = self.client.get(url, {"branch": 999999})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 0


@pytest.mark.django_db
class TestDepartmentAPI(APITestMixin):
    """Test cases for Department API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    def test_create_department(self, branch):
        """Test creating a department via API"""
        # Create a Support block as function field is often required/validated against it
        support_block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=branch,
        )

        dept_data = {
            "name": "Phòng Nhân sự",
            "branch_id": str(branch.id),
            "block_id": str(support_block.id),
            "function": Department.DepartmentFunction.HR_ADMIN,  # Required for support blocks
        }

        url = reverse("hrm:department-list")
        response = self.client.post(url, dept_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Department.objects.count() == 1

    def test_department_tree_endpoint(self, branch, block):
        """Test department tree structure endpoint"""
        parent_dept = Department.objects.create(name="Phòng Nhân sự", branch=branch, block=block)
        Department.objects.create(
            name="Ban Tuyển dụng",
            branch=branch,
            block=block,
            parent_department=parent_dept,
        )

        url = reverse("hrm:department-tree")
        response = self.client.get(url, {"block_id": str(block.id)})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1  # One root department
        assert len(response_data[0]["children"]) == 1  # One child

    def test_filter_departments_by_invalid_block_returns_empty(self, branch, block):
        Department.objects.create(
            name="Phòng Nhân sự",
            branch=branch,
            block=block,
        )

        url = reverse("hrm:department-list")
        response = self.client.get(url, {"block": 999999})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 0


@pytest.mark.django_db
class TestPositionAPI(APITestMixin):
    """Test cases for Position API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

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
class TestAPIFilteringAndSearch(APITestMixin):
    """Test cases for API filtering and search functionality"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    def test_branch_search(self, province, admin_unit):
        """Test branch search functionality"""
        Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=province,
            administrative_unit=admin_unit,
        )
        Branch.objects.create(
            name="Chi nhánh TP.HCM",
            code="HCM",
            province=province,
            administrative_unit=admin_unit,
        )

        url = reverse("hrm:branch-list")
        response = self.client.get(url, {"search": "Hà Nội"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == "HN"

    def test_block_filtering_by_branch(self, province, admin_unit):
        """Test block filtering by branch"""
        branch1 = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=province,
            administrative_unit=admin_unit,
        )

        Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=branch1,
        )
        Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=branch1,
        )

        url = reverse("hrm:block-list")
        response = self.client.get(url, {"branch_code": "HN"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2  # Both blocks belong to HN branch

    def test_block_filtering_by_type(self, branch):
        """Test block filtering by type"""
        Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=branch,
        )
        Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=branch,
        )

        url = reverse("hrm:block-list")
        response = self.client.get(url, {"block_type": Block.BlockType.SUPPORT})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == "HT"
