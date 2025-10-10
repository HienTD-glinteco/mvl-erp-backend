from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.hrm.models import Block, Branch, Department

User = get_user_model()


class DepartmentEnhancementsModelTest(TestCase):
    """Test cases for enhanced Department model according to SRS 2.3.2"""

    def setUp(self):
        self.branch = Branch.objects.create(name="Chi nhánh Hà Nội", code="HN")
        self.support_block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        self.business_block = Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )

    def test_department_function_auto_set_for_business_block(self):
        """Test function auto-set to 'business' for business blocks"""
        dept = Department.objects.create(name="Phòng Kinh doanh 1", branch=self.branch, block=self.business_block)
        # Function should be auto-set to business
        self.assertEqual(dept.function, Department.DepartmentFunction.BUSINESS)
        # Branch should be auto-set from block
        self.assertEqual(dept.branch, self.branch)

    def test_department_branch_auto_set_from_block(self):
        """Test branch auto-set from block when not explicitly provided"""
        dept = Department.objects.create(
            name="Phòng Test",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )
        # Branch should be auto-set from block.branch
        self.assertEqual(dept.branch, self.branch)
        self.assertEqual(dept.branch, dept.block.branch)

    def test_department_function_choices_for_support_block(self):
        """Test available function choices for support blocks"""
        choices = Department.get_function_choices_for_block_type(Block.BlockType.SUPPORT)
        expected_functions = [
            "hr_admin",
            "recruit_training",
            "marketing",
            "business_secretary",
            "accounting",
            "trading_floor",
            "project_promotion",
            "project_development",
        ]
        actual_functions = [choice[0] for choice in choices]

        for func in expected_functions:
            self.assertIn(func, actual_functions)

    def test_department_function_choices_for_business_block(self):
        """Test available function choices for business blocks"""
        choices = Department.get_function_choices_for_block_type(Block.BlockType.BUSINESS)
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0][0], Department.DepartmentFunction.BUSINESS)

    def test_main_department_validation(self):
        """Test only one main department per function validation"""
        # Create first main department
        dept1 = Department.objects.create(  # NOQA
            name="Phòng Nhân sự chính",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
            is_main_department=True,
        )

        # Try to create another main department with same function - should fail
        dept2 = Department(
            name="Phòng Nhân sự phụ",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
            is_main_department=True,
        )

        with self.assertRaises(ValidationError) as context:
            dept2.clean()

        self.assertIn("is_main_department", context.exception.message_dict)

    def test_management_department_validation(self):
        """Test management department must be same block and function"""
        # Create departments
        hr_dept = Department.objects.create(
            name="Phòng Nhân sự",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        accounting_dept = Department.objects.create(
            name="Phòng Kế toán",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.ACCOUNTING,
        )

        # Try to set management department with different function - should fail
        hr_dept.management_department = accounting_dept

        with self.assertRaises(ValidationError) as context:
            hr_dept.clean()

        self.assertIn("management_department", context.exception.message_dict)

    def test_management_department_same_function_allowed(self):
        """Test management department with same function is allowed"""
        # Create two HR departments
        hr_main = Department.objects.create(
            name="Phòng Nhân sự chính",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
            is_main_department=True,
        )

        hr_sub = Department.objects.create(
            name="Ban Tuyển dụng",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
            management_department=hr_main,
        )

        # This should pass validation
        hr_sub.clean()
        self.assertEqual(hr_sub.management_department, hr_main)

    def test_management_department_self_reference_model(self):
        """Test that a department cannot manage itself at model level"""
        dept = Department.objects.create(
            name="Phòng Hành chính",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        # Try to set management department to itself
        dept.management_department = dept

        with self.assertRaises(ValidationError) as context:
            dept.clean()

        self.assertIn("management_department", context.exception.message_dict)
        self.assertIn(
            "cannot manage itself",
            str(context.exception.message_dict["management_department"][0]),
        )


class DepartmentEnhancementsAPITest(APITestCase):
    """Test cases for enhanced Department API according to SRS 2.3.2"""

    def setUp(self):
        # Clear all existing data for clean tests
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.branch = Branch.objects.create(name="Chi nhánh Hà Nội", code="HN")
        self.support_block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        self.business_block = Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        import json

        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def get_response_error(self, response):
        """Extract error from wrapped API response"""
        import json

        content = json.loads(response.content.decode())
        return content.get("error")

    def test_function_choices_endpoint(self):
        """Test function choices endpoint"""
        url = reverse("hrm:department-function-choices")

        # Test support block function choices
        response = self.client.get(url, {"block_type": "support"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = self.get_response_data(response)
        self.assertEqual(data["block_type"], "support")
        self.assertEqual(len(data["functions"]), 8)

        # Check specific functions are present
        function_values = [f["value"] for f in data["functions"]]
        self.assertIn("hr_admin", function_values)
        self.assertIn("accounting", function_values)

    def test_function_choices_business_block(self):
        """Test function choices for business block"""
        url = reverse("hrm:department-function-choices")

        response = self.client.get(url, {"block_type": "business"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = self.get_response_data(response)
        self.assertEqual(data["block_type"], "business")
        self.assertEqual(len(data["functions"]), 1)
        self.assertEqual(data["functions"][0]["value"], "business")

    def test_function_choices_missing_parameter(self):
        """Test function choices endpoint with missing parameter"""
        url = reverse("hrm:department-function-choices")

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_management_choices_endpoint(self):
        """Test management department choices endpoint"""
        # Create HR departments
        hr_main = Department.objects.create(  # NOQA
            name="Phòng Nhân sự chính",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        hr_sub = Department.objects.create(  # NOQA
            name="Ban Đào tạo",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        url = reverse("hrm:department-management-choices")
        response = self.client.get(url, {"block_id": str(self.support_block.id), "function": "hr_admin"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

        # Check department info is included
        dept_names = [d["name"] for d in data]
        self.assertIn("Phòng Nhân sự chính", dept_names)
        self.assertIn("Ban Đào tạo", dept_names)

    def test_create_department_with_function_auto_set(self):
        """Test creating department with auto-set function for business block"""
        url = reverse("hrm:department-list")
        dept_data = {
            "name": "Phòng Kinh doanh 1",
            "branch_id": str(self.branch.id),
            "block_id": str(self.business_block.id),
            # Don't specify function - should be auto-set
        }

        response = self.client.post(url, dept_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check department was created with business function
        data = self.get_response_data(response)
        dept = Department.objects.get(id=data["id"])
        self.assertEqual(dept.function, Department.DepartmentFunction.BUSINESS)

    def test_create_department_with_invalid_function_for_block_type(self):
        """Test creating department with invalid function for block type"""
        url = reverse("hrm:department-list")
        dept_data = {
            "name": "Phòng Test",
            "branch_id": str(self.branch.id),
            "block_id": str(self.business_block.id),
            "function": "hr_admin",  # Invalid for business block
        }

        response = self.client.post(url, dept_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_department_serializer_includes_new_fields(self):
        """Test department serializer includes all new fields"""
        dept = Department.objects.create(
            name="Phòng Nhân sự",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
            is_main_department=True,
        )

        url = reverse("hrm:department-detail", kwargs={"pk": dept.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check new fields are present
        self.assertIn("branch", data)
        self.assertIn("block", data)
        self.assertIn("function", data)
        self.assertIn("function_display", data)
        self.assertIn("is_main_department", data)
        self.assertIn("management_department", data)
        self.assertIn("available_function_choices", data)
        self.assertIn("available_management_departments", data)

        # Check values
        self.assertEqual(data["function"], "hr_admin")
        self.assertEqual(data["function_display"], "HR Administration")
        self.assertTrue(data["is_main_department"])
        self.assertIsNotNone(data["branch"])
        self.assertIsNotNone(data["block"])

    def test_support_block_gets_default_function_api(self):
        """Test that support blocks get default function if not specified via API"""
        url = reverse("hrm:department-list")
        dept_data = {
            "name": "Phòng Hành chính",
            "branch_id": str(self.branch.id),
            "block_id": str(self.support_block.id),
            # Note: no function specified - should get default HR_ADMIN
        }

        response = self.client.post(url, dept_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = self.get_response_data(response)
        self.assertEqual(data["function"], Department.DepartmentFunction.HR_ADMIN)

    def test_support_block_cannot_have_business_function_api(self):
        """Test that support blocks cannot have business function via API"""
        url = reverse("hrm:department-list")
        dept_data = {
            "name": "Phòng Hành chính",
            "branch_id": str(self.branch.id),
            "block_id": str(self.support_block.id),
            "function": Department.DepartmentFunction.BUSINESS,
        }

        response = self.client.post(url, dept_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        error = self.get_response_error(response)
        # drf-standardized-errors: collect attrs from errors list
        fields = set()
        if isinstance(error, dict) and isinstance(error.get("errors"), list):
            fields = {e.get("attr") for e in error["errors"] if e.get("attr")}
        self.assertIn("function", fields)

    def test_management_department_self_reference_api(self):
        """Test that a department cannot manage itself via API"""
        # Create a department first
        dept = Department.objects.create(
            name="Phòng Hành chính",
            branch=self.branch,
            block=self.support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        # Try to update it to manage itself
        url = reverse("hrm:department-detail", kwargs={"pk": dept.id})
        update_data = {
            "name": dept.name,
            "branch_id": str(dept.branch.id),
            "block_id": str(dept.block.id),
            "function": dept.function,
            "management_department": str(dept.id),
        }

        response = self.client.put(url, update_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        error = self.get_response_error(response)
        fields = set()
        if isinstance(error, dict) and isinstance(error.get("errors"), list):
            fields = {e.get("attr") for e in error["errors"] if e.get("attr")}
        self.assertIn("management_department", fields)
