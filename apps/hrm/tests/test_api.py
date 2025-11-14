import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Position

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


class BranchAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Branch API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        Position.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create Province and AdministrativeUnit for Branch tests
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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Branch.objects.count(), 1)

        branch = Branch.objects.first()
        self.assertEqual(branch.name, self.branch_data["name"])
        # Code is now auto-generated, not from provided data
        self.assertTrue(branch.code.startswith("CN"))

    def test_list_branches(self):
        """Test listing branches via API"""
        Branch.objects.create(
            name=self.branch_data["name"],
            code=self.branch_data["code"],
            address=self.branch_data["address"],
            phone=self.branch_data["phone"],
            email=self.branch_data["email"],
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        url = reverse("hrm:branch-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], self.branch_data["name"])

    def test_retrieve_branch(self):
        """Test retrieving a branch via API"""
        branch = Branch.objects.create(
            name=self.branch_data["name"],
            code=self.branch_data["code"],
            address=self.branch_data["address"],
            phone=self.branch_data["phone"],
            email=self.branch_data["email"],
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], branch.name)

    def test_update_branch(self):
        """Test updating a branch via API"""
        branch = Branch.objects.create(
            name=self.branch_data["name"],
            code=self.branch_data["code"],
            address=self.branch_data["address"],
            phone=self.branch_data["phone"],
            email=self.branch_data["email"],
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        update_data = {"name": "Chi nhánh Hà Nội Updated"}
        url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        response = self.client.patch(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        branch.refresh_from_db()
        self.assertEqual(branch.name, update_data["name"])

    def test_delete_branch(self):
        """Test deleting a branch via API"""
        branch = Branch.objects.create(
            name=self.branch_data["name"],
            code=self.branch_data["code"],
            address=self.branch_data["address"],
            phone=self.branch_data["phone"],
            email=self.branch_data["email"],
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Branch.objects.count(), 0)


class BlockAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Block API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        Position.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

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

        self.branch = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

    def test_create_block(self):
        """Test creating a block via API"""
        block_data = {
            "name": "Khối Hỗ trợ",
            "code": "HT",  # This code should be ignored
            "block_type": Block.BlockType.SUPPORT,
            "branch_id": str(self.branch.id),
        }

        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Block.objects.count(), 1)

        block = Block.objects.first()
        self.assertEqual(block.name, block_data["name"])
        self.assertEqual(block.block_type, block_data["block_type"])
        # Verify auto-generated code (should not be "HT")
        self.assertNotEqual(block.code, "HT")
        self.assertTrue(block.code.startswith("KH"))

    def test_list_blocks_with_filtering(self):
        """Test listing blocks with filtering"""
        support_block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        business_block = Block.objects.create(
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


class DepartmentAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Department API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        Position.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

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

        self.branch = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )
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
            "branch_id": str(self.branch.id),
            "block_id": str(self.block.id),
            "function": Department.DepartmentFunction.HR_ADMIN,  # Required for support blocks
        }

        url = reverse("hrm:department-list")
        response = self.client.post(url, dept_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Department.objects.count(), 1)

    def test_department_tree_endpoint(self):
        """Test department tree structure endpoint"""
        parent_dept = Department.objects.create(name="Phòng Nhân sự", branch=self.branch, block=self.block)
        child_dept = Department.objects.create(
            name="Ban Tuyển dụng",
            branch=self.branch,
            block=self.block,
            parent_department=parent_dept,
        )

        url = reverse("hrm:department-tree")
        response = self.client.get(url, {"block_id": str(self.block.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)  # One root department
        self.assertEqual(len(response_data[0]["children"]), 1)  # One child


class PositionAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Position API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        Position.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_position(self):
        """Test creating a position via API"""
        position_data = {
            "name": "Tổng Giám đốc",
            "code": "TGD",
        }

        url = reverse("hrm:position-list")
        response = self.client.post(url, position_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Position.objects.count(), 1)

    def test_position_ordering(self):
        """Test position ordering in API response"""
        Position.objects.create(name="Nhân viên", code="NV")
        Position.objects.create(name="Tổng Giám đốc", code="TGD")
        Position.objects.create(name="Giám đốc", code="GD")

        url = reverse("hrm:position-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Should be ordered by name alphabetically (Giám đốc, Nhân viên, Tổng Giám đốc)
        self.assertEqual(response_data[0]["code"], "GD")
        self.assertEqual(response_data[1]["code"], "NV")
        self.assertEqual(response_data[2]["code"], "TGD")


# OrganizationChartAPITest class removed as OrganizationChart API endpoints no longer exist
# Employee-based API should be used instead
class APIFilteringAndSearchTest(TransactionTestCase, APITestMixin):
    """Test cases for API filtering and search functionality"""

    def setUp(self):
        # Clear all existing data for clean tests
        Branch.objects.all().delete()
        Block.objects.all().delete()
        Department.objects.all().delete()
        Position.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

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

        # Create test data
        self.branch1 = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )
        self.branch2 = Branch.objects.create(
            name="Chi nhánh TP.HCM",
            code="HCM",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.block1 = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch1,
        )
        self.block2 = Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch1,
        )

    def test_branch_search(self):
        """Test branch search functionality"""
        url = reverse("hrm:branch-list")
        response = self.client.get(url, {"search": "Hà Nội"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], "HN")

    def test_block_filtering_by_branch(self):
        """Test block filtering by branch"""
        url = reverse("hrm:block-list")
        response = self.client.get(url, {"branch_code": "HN"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)  # Both blocks belong to HN branch

    def test_block_filtering_by_type(self):
        """Test block filtering by type"""
        url = reverse("hrm:block-list")
        response = self.client.get(url, {"block_type": Block.BlockType.SUPPORT})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], "HT")
