import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import RecruitmentRequest
from libs import ColorVariant


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
class TestRecruitmentRequestAPI(APITestMixin):
    """Test cases for RecruitmentRequest API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def request_data(self, job_description, department, employee):
        return {
            "name": "Backend Developer Position",
            "job_description_id": job_description.id,
            "department_id": department.id,
            "proposer_id": employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 2,
        }

    def test_create_recruitment_request(self, request_data, department):
        """Test creating a recruitment request via API"""
        url = reverse("hrm:recruitment-request-list")
        response = self.client.post(url, request_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert RecruitmentRequest.objects.count() == 1

        request = RecruitmentRequest.objects.first()
        assert request.name == request_data["name"]
        assert request.job_description_id == request_data["job_description_id"]
        assert request.department_id == request_data["department_id"]
        assert request.proposer_id == request_data["proposer_id"]
        assert request.recruitment_type == request_data["recruitment_type"]
        assert request.status == request_data["status"]
        assert request.proposed_salary == request_data["proposed_salary"]
        assert request.number_of_positions == request_data["number_of_positions"]

        # Verify code was auto-generated
        assert request.code.startswith("RR")

        # Verify branch and block were auto-set from department
        assert request.branch == department.branch
        assert request.block == department.block

    def test_create_without_branch_and_block(self, request_data, department):
        """Test that branch and block are auto-set from department"""
        url = reverse("hrm:recruitment-request-list")
        # Don't include branch_id and block_id in request
        data = request_data.copy()
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        request = RecruitmentRequest.objects.first()

        # Branch and block should be auto-set
        assert request.branch == department.branch
        assert request.block == department.block

    def test_create_with_minimal_fields(self, job_description, department, employee):
        """Test creating a recruitment request with only required fields"""
        url = reverse("hrm:recruitment-request-list")
        minimal_data = {
            "name": "Backend Developer Position",
            "job_description_id": job_description.id,
            "department_id": department.id,
            "proposer_id": employee.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "2000-3000 USD",
        }
        response = self.client.post(url, minimal_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert RecruitmentRequest.objects.count() == 1

        request = RecruitmentRequest.objects.first()
        assert request.status == "DRAFT"  # Default status
        assert request.number_of_positions == 1  # Default value

    def test_list_recruitment_requests(self, request_data):
        """Test listing recruitment requests via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-request-list")
        self.client.post(url, request_data, format="json")

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == request_data["name"]

        # Check nested objects are returned
        assert "job_description" in response_data[0]
        assert "branch" in response_data[0]
        assert "block" in response_data[0]
        assert "department" in response_data[0]
        assert "proposer" in response_data[0]

    def test_retrieve_recruitment_request(self, request_data):
        """Test retrieving a recruitment request via API"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == request_data["name"]
        assert response_data["colored_recruitment_type"]["value"] == request_data["recruitment_type"]

    def test_update_recruitment_request(self, request_data, job_description, department, employee):
        """Test updating a recruitment request via API"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        update_data = {
            "name": "Backend Developer Position - Updated",
            "job_description_id": job_description.id,
            "department_id": department.id,
            "proposer_id": employee.id,
            "recruitment_type": "REPLACEMENT",
            "status": "OPEN",
            "proposed_salary": "2500-3500 USD",
            "number_of_positions": 3,
        }

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.put(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == update_data["name"]
        assert response_data["colored_recruitment_type"]["value"] == update_data["recruitment_type"]
        assert response_data["colored_status"]["value"] == update_data["status"]
        assert response_data["proposed_salary"] == update_data["proposed_salary"]
        assert response_data["number_of_positions"] == update_data["number_of_positions"]

    def test_partial_update_recruitment_request(self, request_data):
        """Test partially updating a recruitment request via API"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        partial_data = {
            "status": "PAUSED",
            "number_of_positions": 1,
        }

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.patch(url, partial_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["colored_status"]["value"] == partial_data["status"]
        assert response_data["number_of_positions"] == partial_data["number_of_positions"]
        # Other fields should remain unchanged
        assert response_data["name"] == request_data["name"]
        assert response_data["colored_recruitment_type"]["value"] == request_data["recruitment_type"]

    def test_delete_draft_recruitment_request(self, request_data):
        """Test deleting a recruitment request with DRAFT status"""
        # Create via API with DRAFT status
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert RecruitmentRequest.objects.count() == 0

    def test_delete_non_draft_recruitment_request_fails(self, request_data):
        """Test that deleting a non-DRAFT recruitment request fails"""
        # Create via API with OPEN status
        data = request_data.copy()
        data["status"] = "OPEN"
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert RecruitmentRequest.objects.count() == 1

        # Check error message
        content = response.json()
        assert "error" in content

    def test_filter_by_status(self, request_data):
        """Test filtering recruitment requests by status"""
        url = reverse("hrm:recruitment-request-list")

        # Create requests with different statuses
        data1 = request_data.copy()
        data1["status"] = "DRAFT"
        data1["name"] = "Position 1"
        self.client.post(url, data1, format="json")

        data2 = request_data.copy()
        data2["status"] = "OPEN"
        data2["name"] = "Position 2"
        self.client.post(url, data2, format="json")

        # Filter by DRAFT status
        response = self.client.get(url, {"status": "DRAFT"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["colored_status"]["value"] == "DRAFT"

    def test_filter_by_recruitment_type(self, request_data):
        """Test filtering recruitment requests by recruitment type"""
        url = reverse("hrm:recruitment-request-list")

        # Create requests with different types
        data1 = request_data.copy()
        data1["recruitment_type"] = "NEW_HIRE"
        data1["name"] = "Position 1"
        self.client.post(url, data1, format="json")

        data2 = request_data.copy()
        data2["recruitment_type"] = "REPLACEMENT"
        data2["name"] = "Position 2"
        self.client.post(url, data2, format="json")

        # Filter by NEW_HIRE type
        response = self.client.get(url, {"recruitment_type": "NEW_HIRE"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["colored_recruitment_type"]["value"] == "NEW_HIRE"

    def test_filter_by_department(self, request_data, department):
        """Test filtering recruitment requests by department"""
        url = reverse("hrm:recruitment-request-list")

        # Create request
        self.client.post(url, request_data, format="json")

        # Filter by department
        response = self.client.get(url, {"department": department.id})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["department"]["id"] == department.id

    def test_search_by_name(self, request_data):
        """Test searching recruitment requests by name"""
        url = reverse("hrm:recruitment-request-list")

        # Create multiple requests
        data1 = request_data.copy()
        data1["name"] = "Senior Backend Developer"
        self.client.post(url, data1, format="json")

        data2 = request_data.copy()
        data2["name"] = "Junior Frontend Developer"
        self.client.post(url, data2, format="json")

        # Search by name
        response = self.client.get(url, {"search": "Backend"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert "Backend" in response_data[0]["name"]

    def test_search_by_code(self, request_data):
        """Test searching recruitment requests by code"""
        url = reverse("hrm:recruitment-request-list")

        # Create a request
        create_response = self.client.post(url, request_data, format="json")
        code = self.get_response_data(create_response)["code"]

        # Search by code
        response = self.client.get(url, {"search": code[:4]})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == code

    def test_ordering_by_created_at(self, request_data):
        """Test ordering recruitment requests by created_at"""
        url = reverse("hrm:recruitment-request-list")

        # Create multiple requests
        data1 = request_data.copy()
        data1["name"] = "Position 1"
        self.client.post(url, data1, format="json")

        data2 = request_data.copy()
        data2["name"] = "Position 2"
        self.client.post(url, data2, format="json")

        # Default ordering is -created_at (descending)
        response = self.client.get(url)
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        assert response_data[0]["name"] == "Position 2"
        assert response_data[1]["name"] == "Position 1"

    def test_ordering_by_name(self, request_data):
        """Test ordering recruitment requests by name"""
        url = reverse("hrm:recruitment-request-list")

        # Create multiple requests
        data1 = request_data.copy()
        data1["name"] = "Zulu Position"
        self.client.post(url, data1, format="json")

        data2 = request_data.copy()
        data2["name"] = "Alpha Position"
        self.client.post(url, data2, format="json")

        # Order by name ascending
        response = self.client.get(url, {"ordering": "name"})
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        assert response_data[0]["name"] == "Alpha Position"
        assert response_data[1]["name"] == "Zulu Position"

    def test_auto_code_generation(self, request_data):
        """Test that recruitment request code is auto-generated correctly"""
        url = reverse("hrm:recruitment-request-list")
        response = self.client.post(url, request_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Code should start with RR prefix
        assert response_data["code"].startswith("RR")
        # Code should not be empty
        assert len(response_data["code"]) > 2

    def test_code_is_readonly(self, request_data):
        """Test that code field is read-only and cannot be modified via API"""
        url = reverse("hrm:recruitment-request-list")
        data_with_code = request_data.copy()
        data_with_code["code"] = "CUSTOM_CODE"

        response = self.client.post(url, data_with_code, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        # Code should be auto-generated, not the custom one
        assert response_data["code"] != "CUSTOM_CODE"
        assert response_data["code"].startswith("RR")

    def test_validate_number_of_positions(self, request_data):
        """Test validation for number of positions"""
        url = reverse("hrm:recruitment-request-list")
        data = request_data.copy()
        data["number_of_positions"] = 0

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.json()
        assert "error" in content

    def test_required_fields(self, request_data):
        """Test that required fields are validated"""
        url = reverse("hrm:recruitment-request-list")

        # Test without name
        data = request_data.copy()
        del data["name"]
        response = self.client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Test without job_description_id
        data = request_data.copy()
        del data["job_description_id"]
        response = self.client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Note: department_id is optional (can be null)

        # Test without proposer_id
        data = request_data.copy()
        del data["proposer_id"]
        response = self.client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Test without recruitment_type
        data = request_data.copy()
        del data["recruitment_type"]
        response = self.client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Test without proposed_salary
        data = request_data.copy()
        del data["proposed_salary"]
        response = self.client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_colored_status_in_response(self, request_data):
        """Test that colored_status field is included in API response"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        # Retrieve the request
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Check colored_status is present and has correct structure
        assert "colored_status" in response_data
        colored_status = response_data["colored_status"]
        assert colored_status["value"] == "DRAFT"
        assert colored_status["variant"] == ColorVariant.GREY

    def test_colored_recruitment_type_in_response(self, request_data):
        """Test that colored_recruitment_type field is included in API response"""
        # Create via API
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        # Retrieve the request
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Check colored_recruitment_type is present and has correct structure
        assert "colored_recruitment_type" in response_data
        colored_recruitment_type = response_data["colored_recruitment_type"]
        assert colored_recruitment_type["value"] == "NEW_HIRE"
        assert colored_recruitment_type["variant"] == ColorVariant.BLUE

    def test_colored_status_variants_for_all_statuses(self, request_data):
        """Test that all status values return correct color variants"""
        url = reverse("hrm:recruitment-request-list")

        test_cases = [
            ("DRAFT", ColorVariant.GREY),
            ("OPEN", ColorVariant.GREEN),
            ("PAUSED", ColorVariant.YELLOW),
            ("CLOSED", ColorVariant.RED),
        ]

        for status_value, expected_variant in test_cases:
            data = request_data.copy()
            data["status"] = status_value
            data["name"] = f"Position {status_value}"

            create_response = self.client.post(url, data, format="json")
            request_id = self.get_response_data(create_response)["id"]

            detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
            response = self.client.get(detail_url)

            response_data = self.get_response_data(response)
            colored_status = response_data["colored_status"]
            assert colored_status["value"] == status_value
            assert colored_status["variant"] == expected_variant

    def test_colored_recruitment_type_variants(self, request_data):
        """Test that all recruitment type values return correct color variants"""
        url = reverse("hrm:recruitment-request-list")

        test_cases = [
            ("NEW_HIRE", ColorVariant.BLUE),
            ("REPLACEMENT", ColorVariant.PURPLE),
        ]

        for type_value, expected_variant in test_cases:
            data = request_data.copy()
            data["recruitment_type"] = type_value
            data["name"] = f"Position {type_value}"

            create_response = self.client.post(url, data, format="json")
            request_id = self.get_response_data(create_response)["id"]

            detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
            response = self.client.get(detail_url)

            response_data = self.get_response_data(response)
            colored_recruitment_type = response_data["colored_recruitment_type"]
            assert colored_recruitment_type["value"] == type_value
            assert colored_recruitment_type["variant"] == expected_variant

    def test_number_of_candidates_field(self, request_data):
        """Test that number_of_candidates field is included and accurate"""
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        # Initially should be 0
        detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(detail_url)
        response_data = self.get_response_data(response)

        assert "number_of_candidates" in response_data
        assert response_data["number_of_candidates"] == 0

    def test_number_of_hires_field(self, request_data):
        """Test that number_of_hires field is included and accurate"""
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        # Initially should be 0
        detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(detail_url)
        response_data = self.get_response_data(response)

        assert "number_of_hires" in response_data
        assert response_data["number_of_hires"] == 0

    def test_number_fields_are_read_only(self, request_data):
        """Test that number_of_candidates and number_of_hires are read-only"""
        url = reverse("hrm:recruitment-request-list")

        # Try to set these fields in create
        data = request_data.copy()
        data["number_of_candidates"] = 100
        data["number_of_hires"] = 50

        create_response = self.client.post(url, data, format="json")
        assert create_response.status_code == status.HTTP_201_CREATED

        response_data = self.get_response_data(create_response)

        # These fields should be 0 (ignored from request), not the values we tried to set
        assert response_data["number_of_candidates"] == 0
        assert response_data["number_of_hires"] == 0

    def test_all_fields_in_list_response(self, request_data):
        """Test that all fields including new ones are present in list response"""
        url = reverse("hrm:recruitment-request-list")
        self.client.post(url, request_data, format="json")

        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

        response_data = self.get_response_data(response)
        assert len(response_data) == 1

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
            assert field in item, f"Field '{field}' is missing from response"

    def test_all_fields_in_detail_response(self, request_data):
        """Test that all fields including new ones are present in detail response"""
        url = reverse("hrm:recruitment-request-list")
        create_response = self.client.post(url, request_data, format="json")
        request_id = self.get_response_data(create_response)["id"]

        detail_url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request_id})
        response = self.client.get(detail_url)

        assert response.status_code == status.HTTP_200_OK
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
            assert field in response_data, f"Field '{field}' is missing from response"
