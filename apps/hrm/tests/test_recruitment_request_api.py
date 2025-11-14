import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentRequest,
)
from libs import ColorVariant

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


class RecruitmentRequestAPITest(TransactionTestCase, APITestMixin):
    """Test cases for RecruitmentRequest API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        RecruitmentRequest.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        JobDescription.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        self.department = Department.objects.create(
            name="IT Department",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )

        # Create employee as proposer
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            phone="0123456789",
            attendance_code="EMP001",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            responsibility="Develop backend services",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )

        self.request_data = {
            "name": "Backend Developer Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 2,
        }

    def test_create_recruitment_request(self):
        """Test creating a recruitment request via API"""
        url = reverse("hrm:recruitment-request-list")
        response = self.client.post(url, self.request_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecruitmentRequest.objects.count(), 1)

        request = RecruitmentRequest.objects.first()
        self.assertEqual(request.name, self.request_data["name"])
        self.assertEqual(request.job_description_id, self.request_data["job_description_id"])
        self.assertEqual(request.department_id, self.request_data["department_id"])
        self.assertEqual(request.proposer_id, self.request_data["proposer_id"])
        self.assertEqual(request.recruitment_type, self.request_data["recruitment_type"])
        self.assertEqual(request.status, self.request_data["status"])
        self.assertEqual(request.proposed_salary, self.request_data["proposed_salary"])
        self.assertEqual(request.number_of_positions, self.request_data["number_of_positions"])

        # Verify code was auto-generated
        self.assertTrue(request.code.startswith("RR"))

        # Verify branch and block were auto-set from department
        self.assertEqual(request.branch, self.department.branch)
        self.assertEqual(request.block, self.department.block)

    def test_create_without_branch_and_block(self):
        """Test that branch and block are auto-set from department"""
        url = reverse("hrm:recruitment-request-list")
        # Don't include branch_id and block_id in request
        data = self.request_data.copy()
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        request = RecruitmentRequest.objects.first()

        # Branch and block should be auto-set
        self.assertEqual(request.branch, self.department.branch)
        self.assertEqual(request.block, self.department.block)

    def test_create_with_minimal_fields(self):
        """Test creating a recruitment request with only required fields"""
        url = reverse("hrm:recruitment-request-list")
        minimal_data = {
            "name": "Backend Developer Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "2000-3000 USD",
        }
        response = self.client.post(url, minimal_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecruitmentRequest.objects.count(), 1)

        request = RecruitmentRequest.objects.first()
        self.assertEqual(request.status, "DRAFT")  # Default status
        self.assertEqual(request.number_of_positions, 1)  # Default value

    def test_list_recruitment_requests(self):
        """Test listing recruitment requests via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-request-list")
        self.client.post(url, self.request_data, format="json")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], self.request_data["name"])

        # Check nested objects are returned
        self.assertIn("job_description", response_data[0])
        self.assertIn("branch", response_data[0])
        self.assertIn("block", response_data[0])
        self.assertIn("department", response_data[0])
        self.assertIn("proposer", response_data[0])

    def test_retrieve_recruitment_request(self):
        """Test retrieving a recruitment request via API"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], self.request_data["name"])
        self.assertEqual(response_data["colored_recruitment_type"]["value"], self.request_data["recruitment_type"])

    def test_update_recruitment_request(self):
        """Test updating a recruitment request via API"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        update_data = {
            "name": "Backend Developer Position - Updated",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "REPLACEMENT",
            "status": "OPEN",
            "proposed_salary": "2500-3500 USD",
            "number_of_positions": 3,
        }

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.put(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], update_data["name"])
        self.assertEqual(response_data["colored_recruitment_type"]["value"], update_data["recruitment_type"])
        self.assertEqual(response_data["colored_status"]["value"], update_data["status"])
        self.assertEqual(response_data["proposed_salary"], update_data["proposed_salary"])
        self.assertEqual(response_data["number_of_positions"], update_data["number_of_positions"])

    def test_partial_update_recruitment_request(self):
        """Test partially updating a recruitment request via API"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        partial_data = {
            "status": "PAUSED",
            "number_of_positions": 1,
        }

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.patch(url, partial_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["colored_status"]["value"], partial_data["status"])
        self.assertEqual(response_data["number_of_positions"], partial_data["number_of_positions"])
        # Other fields should remain unchanged
        self.assertEqual(response_data["name"], self.request_data["name"])
        self.assertEqual(response_data["colored_recruitment_type"]["value"], self.request_data["recruitment_type"])

    def test_delete_draft_recruitment_request(self):
        """Test deleting a recruitment request with DRAFT status"""
        # Create via API with DRAFT status
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(RecruitmentRequest.objects.count(), 0)

    def test_delete_non_draft_recruitment_request_fails(self):
        """Test that deleting a non-DRAFT recruitment request fails"""
        # Create via API with OPEN status
        data = self.request_data.copy()
        data["status"] = "OPEN"
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(RecruitmentRequest.objects.count(), 1)

        # Check error message
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_filter_by_status(self):
        """Test filtering recruitment requests by status"""
        url = reverse("hrm:recruitment-request-list")

        # Create requests with different statuses
        data1 = self.request_data.copy()
        data1["status"] = "DRAFT"
        data1["name"] = "Position 1"
        self.client.post(url, data1, format="json")

        data2 = self.request_data.copy()
        data2["status"] = "OPEN"
        data2["name"] = "Position 2"
        self.client.post(url, data2, format="json")

        # Filter by DRAFT status
        response = self.client.get(url, {"status": "DRAFT"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["colored_status"]["value"], "DRAFT")

    def test_filter_by_recruitment_type(self):
        """Test filtering recruitment requests by recruitment type"""
        url = reverse("hrm:recruitment-request-list")

        # Create requests with different types
        data1 = self.request_data.copy()
        data1["recruitment_type"] = "NEW_HIRE"
        data1["name"] = "Position 1"
        self.client.post(url, data1, format="json")

        data2 = self.request_data.copy()
        data2["recruitment_type"] = "REPLACEMENT"
        data2["name"] = "Position 2"
        self.client.post(url, data2, format="json")

        # Filter by NEW_HIRE type
        response = self.client.get(url, {"recruitment_type": "NEW_HIRE"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["colored_recruitment_type"]["value"], "NEW_HIRE")

    def test_filter_by_department(self):
        """Test filtering recruitment requests by department"""
        url = reverse("hrm:recruitment-request-list")

        # Create request
        self.client.post(url, self.request_data, format="json")

        # Filter by department
        response = self.client.get(url, {"department": self.department.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["department"]["id"], self.department.id)

    def test_search_by_name(self):
        """Test searching recruitment requests by name"""
        url = reverse("hrm:recruitment-request-list")

        # Create multiple requests
        data1 = self.request_data.copy()
        data1["name"] = "Senior Backend Developer"
        self.client.post(url, data1, format="json")

        data2 = self.request_data.copy()
        data2["name"] = "Junior Frontend Developer"
        self.client.post(url, data2, format="json")

        # Search by name
        response = self.client.get(url, {"search": "Backend"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertIn("Backend", response_data[0]["name"])

    def test_search_by_code(self):
        """Test searching recruitment requests by code"""
        url = reverse("hrm:recruitment-request-list")

        # Create a request
        create_response = self.client.post(url, self.request_data, format="json")
        code = self.get_response_data(create_response)["code"]

        # Search by code
        response = self.client.get(url, {"search": code[:4]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], code)

    def test_ordering_by_created_at(self):
        """Test ordering recruitment requests by created_at"""
        url = reverse("hrm:recruitment-request-list")

        # Create multiple requests
        data1 = self.request_data.copy()
        data1["name"] = "Position 1"
        self.client.post(url, data1, format="json")

        data2 = self.request_data.copy()
        data2["name"] = "Position 2"
        self.client.post(url, data2, format="json")

        # Default ordering is -created_at (descending)
        response = self.client.get(url)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        self.assertEqual(response_data[0]["name"], "Position 2")
        self.assertEqual(response_data[1]["name"], "Position 1")

    def test_ordering_by_name(self):
        """Test ordering recruitment requests by name"""
        url = reverse("hrm:recruitment-request-list")

        # Create multiple requests
        data1 = self.request_data.copy()
        data1["name"] = "Zulu Position"
        self.client.post(url, data1, format="json")

        data2 = self.request_data.copy()
        data2["name"] = "Alpha Position"
        self.client.post(url, data2, format="json")

        # Order by name ascending
        response = self.client.get(url, {"ordering": "name"})
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        self.assertEqual(response_data[0]["name"], "Alpha Position")
        self.assertEqual(response_data[1]["name"], "Zulu Position")

    def test_auto_code_generation(self):
        """Test that recruitment request code is auto-generated correctly"""
        url = reverse("hrm:recruitment-request-list")
        response = self.client.post(url, self.request_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Code should start with RR prefix
        self.assertTrue(response_data["code"].startswith("RR"))
        # Code should not be empty
        self.assertTrue(len(response_data["code"]) > 2)

    def test_code_is_readonly(self):
        """Test that code field is read-only and cannot be modified via API"""
        url = reverse("hrm:recruitment-request-list")
        data_with_code = self.request_data.copy()
        data_with_code["code"] = "CUSTOM_CODE"

        response = self.client.post(url, data_with_code, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        # Code should be auto-generated, not the custom one
        self.assertNotEqual(response_data["code"], "CUSTOM_CODE")
        self.assertTrue(response_data["code"].startswith("RR"))

    def test_validate_number_of_positions(self):
        """Test validation for number of positions"""
        url = reverse("hrm:recruitment-request-list")
        data = self.request_data.copy()
        data["number_of_positions"] = 0

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_required_fields(self):
        """Test that required fields are validated"""
        url = reverse("hrm:recruitment-request-list")

        # Test without name
        data = self.request_data.copy()
        del data["name"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test without job_description_id
        data = self.request_data.copy()
        del data["job_description_id"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Note: department_id is optional (can be null)

        # Test without proposer_id
        data = self.request_data.copy()
        del data["proposer_id"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test without recruitment_type
        data = self.request_data.copy()
        del data["recruitment_type"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test without proposed_salary
        data = self.request_data.copy()
        del data["proposed_salary"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_colored_status_in_response(self):
        """Test that colored_status field is included in API response"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        # Retrieve the request
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Check colored_status is present and has correct structure
        self.assertIn("colored_status", response_data)
        colored_status = response_data["colored_status"]
        self.assertIn("value", colored_status)
        self.assertIn("variant", colored_status)
        self.assertEqual(colored_status["value"], "DRAFT")
        self.assertEqual(colored_status["variant"], ColorVariant.GREY)

    def test_colored_recruitment_type_in_response(self):
        """Test that colored_recruitment_type field is included in API response"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        # Retrieve the request
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Check colored_recruitment_type is present and has correct structure
        self.assertIn("colored_recruitment_type", response_data)
        colored_recruitment_type = response_data["colored_recruitment_type"]
        self.assertIn("value", colored_recruitment_type)
        self.assertIn("variant", colored_recruitment_type)
        self.assertEqual(colored_recruitment_type["value"], "NEW_HIRE")
        self.assertEqual(colored_recruitment_type["variant"], ColorVariant.BLUE)

    def test_colored_status_variants_for_all_statuses(self):
        """Test that all status values return correct color variants"""
        url = reverse("hrm:recruitment-request-list")

        test_cases = [
            ("DRAFT", ColorVariant.GREY),
            ("OPEN", ColorVariant.GREEN),
            ("PAUSED", ColorVariant.YELLOW),
            ("CLOSED", ColorVariant.RED),
        ]

        for status_value, expected_variant in test_cases:
            data = self.request_data.copy()
            data["status"] = status_value
            data["name"] = f"Position {status_value}"

            create_response = self.client.post(url, data, format="json")
            request_id = self.get_response_data(create_response)["id"]

            detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
            response = self.client.get(detail_url)

            response_data = self.get_response_data(response)
            colored_status = response_data["colored_status"]
            self.assertEqual(colored_status["value"], status_value)
            self.assertEqual(colored_status["variant"], expected_variant)

    def test_colored_recruitment_type_variants(self):
        """Test that all recruitment type values return correct color variants"""
        url = reverse("hrm:recruitment-request-list")

        test_cases = [
            ("NEW_HIRE", ColorVariant.BLUE),
            ("REPLACEMENT", ColorVariant.PURPLE),
        ]

        for type_value, expected_variant in test_cases:
            data = self.request_data.copy()
            data["recruitment_type"] = type_value
            data["name"] = f"Position {type_value}"

            create_response = self.client.post(url, data, format="json")
            request_id = self.get_response_data(create_response)["id"]

            detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
            response = self.client.get(detail_url)

            response_data = self.get_response_data(response)
            colored_recruitment_type = response_data["colored_recruitment_type"]
            self.assertEqual(colored_recruitment_type["value"], type_value)
            self.assertEqual(colored_recruitment_type["variant"], expected_variant)

    def test_number_of_candidates_field(self):
        """Test that number_of_candidates field is included and accurate"""
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        # Initially should be 0
        detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(detail_url)
        response_data = self.get_response_data(response)

        self.assertIn("number_of_candidates", response_data)
        self.assertEqual(response_data["number_of_candidates"], 0)

    def test_number_of_hires_field(self):
        """Test that number_of_hires field is included and accurate"""
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        # Initially should be 0
        detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(detail_url)
        response_data = self.get_response_data(response)

        self.assertIn("number_of_hires", response_data)
        self.assertEqual(response_data["number_of_hires"], 0)

    def test_number_fields_are_read_only(self):
        """Test that number_of_candidates and number_of_hires are read-only"""
        url = reverse("hrm:recruitment-request-list")

        # Try to set these fields in create
        data = self.request_data.copy()
        data["number_of_candidates"] = 100
        data["number_of_hires"] = 50

        create_response = self.client.post(url, data, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        response_data = self.get_response_data(create_response)

        # These fields should be 0 (ignored from request), not the values we tried to set
        self.assertEqual(response_data["number_of_candidates"], 0)
        self.assertEqual(response_data["number_of_hires"], 0)

    def test_all_fields_in_list_response(self):
        """Test that all fields including new ones are present in list response"""
        url = reverse("hrm:recruitment-request-list")
        self.client.post(url, self.request_data, format="json")

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)

        item = response_data[0]

        # Check all expected fields are present
        expected_fields = [
            "id",
            "code",
            "name",
            "job_description",
            "branch",
            "block",
            "department",
            "proposer",
            "colored_status",
            "colored_recruitment_type",
            "proposed_salary",
            "number_of_positions",
            "number_of_candidates",
            "number_of_hires",
            "created_at",
            "updated_at",
        ]

        for field in expected_fields:
            self.assertIn(field, item, f"Field '{field}' is missing from response")

    def test_all_fields_in_detail_response(self):
        """Test that all fields including new ones are present in detail response"""
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, self.request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Check all expected fields are present
        expected_fields = [
            "id",
            "code",
            "name",
            "job_description",
            "branch",
            "block",
            "department",
            "proposer",
            "colored_status",
            "colored_recruitment_type",
            "proposed_salary",
            "number_of_positions",
            "number_of_candidates",
            "number_of_hires",
            "created_at",
            "updated_at",
        ]

        for field in expected_fields:
            self.assertIn(field, response_data, f"Field '{field}' is missing from response")
