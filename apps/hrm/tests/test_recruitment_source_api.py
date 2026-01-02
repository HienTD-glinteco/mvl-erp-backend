import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import RecruitmentSource


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
class TestRecruitmentSourceAPI(APITestMixin):
    """Test cases for Recruitment Source API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def source_data(self):
        return {
            "name": "Employee Referral",
            "description": "Candidates referred by current employees",
        }

    def test_create_recruitment_source(self, source_data):
        """Test creating a recruitment source via API"""
        url = reverse("hrm:recruitment-source-list")
        response = self.client.post(url, source_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert RecruitmentSource.objects.count() == 1

        source = RecruitmentSource.objects.first()
        assert source.name == source_data["name"]
        assert source.description == source_data["description"]
        # Verify code was auto-generated
        assert source.code.startswith("RS")

    def test_list_recruitment_sources(self, source_data):
        """Test listing recruitment sources via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        self.client.post(url, source_data, format="json")

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == source_data["name"]
        assert response_data[0]["description"] == source_data["description"]

    def test_retrieve_recruitment_source(self, source_data):
        """Test retrieving a recruitment source via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        create_response = self.client.post(url, source_data, format="json")
        source_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-source-detail", kwargs={"pk": source_id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == source_data["name"]

    def test_update_recruitment_source(self, source_data):
        """Test updating a recruitment source via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        create_response = self.client.post(url, source_data, format="json")
        source_id = self.get_response_data(create_response)["id"]

        update_data = {
            "name": "Employee Referral Updated",
            "description": "Updated description for employee referrals",
        }

        url = reverse("hrm:recruitment-source-detail", kwargs={"pk": source_id})
        response = self.client.put(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        source = RecruitmentSource.objects.get(id=source_id)
        assert source.name == update_data["name"]
        assert source.description == update_data["description"]

    def test_partial_update_recruitment_source(self, source_data):
        """Test partially updating a recruitment source via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        create_response = self.client.post(url, source_data, format="json")
        source_id = self.get_response_data(create_response)["id"]

        update_data = {"description": "Partially updated description"}

        url = reverse("hrm:recruitment-source-detail", kwargs={"pk": source_id})
        response = self.client.patch(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        source = RecruitmentSource.objects.get(id=source_id)

        assert source.description == update_data["description"]
        # Name should remain unchanged
        assert source.name == source_data["name"]

    def test_delete_recruitment_source(self, source_data):
        """Test deleting a recruitment source via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        create_response = self.client.post(url, source_data, format="json")
        source_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-source-detail", kwargs={"pk": source_id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert RecruitmentSource.objects.count() == 0

    def test_search_recruitment_sources(self, source_data):
        """Test searching recruitment sources by name and code"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        self.client.post(
            url,
            {"name": "Employee Referral", "description": "Referred by employees"},
            format="json",
        )
        self.client.post(
            url,
            {"name": "Job Fair", "description": "Recruited at job fairs"},
            format="json",
        )
        self.client.post(
            url,
            {"name": "Campus Recruitment", "description": "Recruited from universities"},
            format="json",
        )

        # Search by name
        response = self.client.get(url, {"search": "Employee"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Employee Referral"

        # Search by code
        response = self.client.get(url, {"search": "RS"})
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # All sources should have RS prefix
        assert len(response_data) == 3

    def test_unique_code_constraint(self, source_data):
        """Test that recruitment source codes are auto-generated and unique"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        response1 = self.client.post(url, source_data, format="json")
        response2 = self.client.post(url, source_data, format="json")

        # Both should succeed with different codes
        assert response1.status_code == status.HTTP_201_CREATED
        assert response2.status_code == status.HTTP_201_CREATED

        data1 = self.get_response_data(response1)
        data2 = self.get_response_data(response2)
        assert data1["code"] != data2["code"]

    def test_ordering_by_created_at_desc(self, source_data):
        """Test that sources are ordered by created_at descending by default"""
        url = reverse("hrm:recruitment-source-list")
        self.client.post(url, {"name": "First Source"}, format="json")
        self.client.post(url, {"name": "Second Source"}, format="json")
        self.client.post(url, {"name": "Third Source"}, format="json")

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3
        # Most recent first
        assert response_data[0]["name"] == "Third Source"
        assert response_data[1]["name"] == "Second Source"
        assert response_data[2]["name"] == "First Source"

    def test_filter_by_name(self, source_data):
        """Test filtering recruitment sources by name"""
        url = reverse("hrm:recruitment-source-list")
        self.client.post(url, {"name": "Employee Referral"}, format="json")
        self.client.post(url, {"name": "Job Fair"}, format="json")
        self.client.post(url, {"name": "Campus Recruitment"}, format="json")

        # Filter by name containing "Referral"
        response = self.client.get(url, {"name": "Referral"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Employee Referral"

    def test_empty_description_allowed(self, source_data):
        """Test that description field can be empty"""
        url = reverse("hrm:recruitment-source-list")
        data = {"name": "Walk-in"}
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        source = RecruitmentSource.objects.first()
        assert source.name == data["name"]
        assert source.description == ""

    def test_allow_referral_defaults_to_false(self, source_data):
        """Test that allow_referral field defaults to False"""
        # Arrange: Create a recruitment source without specifying allow_referral
        url = reverse("hrm:recruitment-source-list")
        data = {"name": "Job Board", "description": "Online job board"}

        # Act: Create the source via API
        response = self.client.post(url, data, format="json")

        # Assert: Check that allow_referral is False by default
        assert response.status_code == status.HTTP_201_CREATED
        source = RecruitmentSource.objects.first()
        assert source.allow_referral is False

        # Assert: Verify it's in the serialized response
        response_data = self.get_response_data(response)
        assert "allow_referral" in response_data
        assert response_data["allow_referral"] is False

    def test_allow_referral_can_be_set_to_true(self, source_data):
        """Test that allow_referral field can be set to True"""
        # Arrange: Prepare data with allow_referral=True
        url = reverse("hrm:recruitment-source-list")
        data = {"name": "Employee Referral", "description": "Referred by employees", "allow_referral": True}

        # Act: Create the source via API
        response = self.client.post(url, data, format="json")

        # Assert: Check that allow_referral is True
        assert response.status_code == status.HTTP_201_CREATED
        source = RecruitmentSource.objects.first()
        assert source.allow_referral is True

        # Assert: Verify it's in the serialized response
        response_data = self.get_response_data(response)
        assert response_data["allow_referral"] is True

    def test_allow_referral_can_be_set_to_false_explicitly(self, source_data):
        """Test that allow_referral field can be set to False explicitly"""
        # Arrange: Prepare data with allow_referral=False
        url = reverse("hrm:recruitment-source-list")
        data = {"name": "Walk-in", "description": "Walk-in candidates", "allow_referral": False}

        # Act: Create the source via API
        response = self.client.post(url, data, format="json")

        # Assert: Check that allow_referral is False
        assert response.status_code == status.HTTP_201_CREATED
        source = RecruitmentSource.objects.first()
        assert source.allow_referral is False

        # Assert: Verify it's in the serialized response
        response_data = self.get_response_data(response)
        assert response_data["allow_referral"] is False

    def test_allow_referral_api_serialization(self, source_data):
        """Test that allow_referral is correctly serialized in API responses"""
        # Arrange: Create sources with different allow_referral values
        url = reverse("hrm:recruitment-source-list")
        self.client.post(
            url, {"name": "Referral Source", "description": "With referral", "allow_referral": True}, format="json"
        )
        self.client.post(
            url,
            {"name": "Non-Referral Source", "description": "Without referral", "allow_referral": False},
            format="json",
        )

        # Act: Retrieve the list via API
        response = self.client.get(url)

        # Assert: Check that both sources have allow_referral in response
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2

        # Assert: Verify the first source has allow_referral=False (most recent first)
        assert "allow_referral" in response_data[0]
        assert response_data[0]["allow_referral"] is False

        # Assert: Verify the second source has allow_referral=True
        assert "allow_referral" in response_data[1]
        assert response_data[1]["allow_referral"] is True

    def test_source_name_cannot_exceed_250_characters(self, source_data):
        """Test that creating a source with name longer than 250 characters fails"""
        url = reverse("hrm:recruitment-source-list")
        data = {
            **source_data,
            "name": "S" * 251,
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.json()
        assert content["success"] is False
        assert "name" in content["error"]["errors"][0]["attr"]
        assert "250" in content["error"]["errors"][0]["detail"]

    def test_source_description_accepts_500_characters(self, source_data):
        """Test that a 500 character description is accepted for recruitment sources"""
        url = reverse("hrm:recruitment-source-list")
        long_description = "D" * 500
        data = {
            **source_data,
            "description": long_description,
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        source = RecruitmentSource.objects.first()
        assert source.description == long_description

    def test_source_description_cannot_exceed_500_characters(self, source_data):
        """Test that descriptions longer than 500 characters are rejected"""
        url = reverse("hrm:recruitment-source-list")
        data = {
            **source_data,
            "description": "X" * 501,
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.json()
        assert content["success"] is False
        assert "description" in content["error"]["errors"][0]["attr"]
        assert "500" in content["error"]["errors"][0]["detail"]
