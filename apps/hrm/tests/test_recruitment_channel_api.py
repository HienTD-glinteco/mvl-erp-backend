import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import RecruitmentChannel


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
class TestRecruitmentChannelAPI(APITestMixin):
    """Test cases for Recruitment Channel API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def channel_data(self):
        return {
            "name": "LinkedIn",
            "belong_to": "job_website",
            "description": "Professional networking platform",
            "is_active": True,
        }

    def test_create_recruitment_channel(self, channel_data):
        """Test creating a recruitment channel via API"""
        url = reverse("hrm:recruitment-channel-list")
        response = self.client.post(url, channel_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert RecruitmentChannel.objects.count() == 1

        channel = RecruitmentChannel.objects.first()
        assert channel.name == channel_data["name"]
        assert channel.belong_to == channel_data["belong_to"]
        # Verify code was auto-generated
        assert channel.code.startswith("CH")

    def test_list_recruitment_channels(self, channel_data):
        """Test listing recruitment channels via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        self.client.post(url, channel_data, format="json")

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == channel_data["name"]
        assert response_data[0]["belong_to"] == channel_data["belong_to"]

    def test_retrieve_recruitment_channel(self, channel_data):
        """Test retrieving a recruitment channel via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        create_response = self.client.post(url, channel_data, format="json")
        channel_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel_id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == channel_data["name"]

    def test_update_recruitment_channel(self, channel_data):
        """Test updating a recruitment channel via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        create_response = self.client.post(url, channel_data, format="json")
        channel_id = self.get_response_data(create_response)["id"]

        update_data = {
            "name": "LinkedIn Updated",
            "belong_to": "marketing",
            "description": "Updated description",
            "is_active": True,
        }

        url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel_id})
        response = self.client.put(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        channel = RecruitmentChannel.objects.get(id=channel_id)
        assert channel.name == update_data["name"]
        assert channel.belong_to == update_data["belong_to"]
        assert channel.description == update_data["description"]

    def test_partial_update_recruitment_channel(self, channel_data):
        """Test partially updating a recruitment channel via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        create_response = self.client.post(url, channel_data, format="json")
        channel_id = self.get_response_data(create_response)["id"]

        update_data = {"is_active": False}

        url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel_id})
        response = self.client.patch(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        channel = RecruitmentChannel.objects.get(id=channel_id)

        assert channel.is_active is False
        # Belong_to should remain unchanged (default or previously set)

    def test_delete_recruitment_channel(self, channel_data):
        """Test deleting a recruitment channel via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        create_response = self.client.post(url, channel_data, format="json")
        channel_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel_id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert RecruitmentChannel.objects.count() == 0

    def test_search_recruitment_channels(self, channel_data):
        """Test searching recruitment channels by name and code"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        self.client.post(
            url,
            {"name": "LinkedIn", "description": "Professional network", "belong_to": "job_website"},
            format="json",
        )
        self.client.post(
            url,
            {"name": "Facebook Jobs", "description": "Social media jobs", "belong_to": "marketing"},
            format="json",
        )
        self.client.post(
            url,
            {"name": "Indeed", "description": "Job search engine", "belong_to": "job_website"},
            format="json",
        )

        # Search by name
        response = self.client.get(url, {"search": "LinkedIn"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "LinkedIn"

        # Search by code
        response = self.client.get(url, {"search": "CH"})
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # All channels should have CH prefix
        assert len(response_data) == 3

    def test_filter_recruitment_channels_by_active_status(self, channel_data):
        """Test filtering recruitment channels by active status"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        self.client.post(
            url,
            {"name": "Active Channel", "is_active": True, "belong_to": "job_website"},
            format="json",
        )
        self.client.post(
            url,
            {"name": "Inactive Channel", "is_active": False, "belong_to": "marketing"},
            format="json",
        )

        # Filter active channels
        response = self.client.get(url, {"is_active": "true"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Active Channel"

        # Filter inactive channels
        response = self.client.get(url, {"is_active": "false"})
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Inactive Channel"

    def test_unique_code_constraint(self, channel_data):
        """Test that recruitment channel codes are auto-generated and unique"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        response1 = self.client.post(url, channel_data, format="json")
        response2 = self.client.post(url, channel_data, format="json")

        # Both should succeed with different codes
        assert response1.status_code == status.HTTP_201_CREATED
        assert response2.status_code == status.HTTP_201_CREATED

        data1 = self.get_response_data(response1)
        data2 = self.get_response_data(response2)
        assert data1["code"] != data2["code"]

    def test_ordering_by_created_at_desc(self, channel_data):
        """Test that channels are ordered by created_at descending by default"""
        url = reverse("hrm:recruitment-channel-list")
        self.client.post(url, {"name": "First Channel", "belong_to": "job_website"}, format="json")
        self.client.post(url, {"name": "Second Channel", "belong_to": "marketing"}, format="json")
        self.client.post(url, {"name": "Third Channel", "belong_to": "job_website"}, format="json")

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3
        # Most recent first
        assert response_data[0]["name"] == "Third Channel"
        assert response_data[1]["name"] == "Second Channel"
        assert response_data[2]["name"] == "First Channel"

    def test_create_channel_with_hunt_belong_to(self, channel_data):
        """Test creating a recruitment channel with HUNT belong_to option"""
        url = reverse("hrm:recruitment-channel-list")
        channel_data = {
            "name": "LinkedIn Recruiter",
            "belong_to": "hunt",
            "description": "Headhunting via LinkedIn",
        }
        response = self.client.post(url, channel_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["belong_to"] == "hunt"
        assert response_data["name"] == "LinkedIn Recruiter"

    def test_create_channel_with_school_belong_to(self, channel_data):
        """Test creating a recruitment channel with SCHOOL belong_to option"""
        url = reverse("hrm:recruitment-channel-list")
        channel_data = {
            "name": "University Job Fair",
            "belong_to": "school",
            "description": "Recruiting from universities",
        }
        response = self.client.post(url, channel_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["belong_to"] == "school"
        assert response_data["name"] == "University Job Fair"

    def test_filter_channels_by_belong_to(self, channel_data):
        """Test filtering recruitment channels by belong_to option"""
        url = reverse("hrm:recruitment-channel-list")

        # Create channels with different belong_to values
        self.client.post(url, {"name": "Indeed", "belong_to": "job_website"}, format="json")
        self.client.post(url, {"name": "Facebook Ads", "belong_to": "marketing"}, format="json")
        self.client.post(url, {"name": "LinkedIn Recruiter", "belong_to": "hunt"}, format="json")
        self.client.post(url, {"name": "University Fair", "belong_to": "school"}, format="json")

        # Filter by hunt
        response = self.client.get(url, {"belong_to": "hunt"})
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "LinkedIn Recruiter"

        # Filter by school
        response = self.client.get(url, {"belong_to": "school"})
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "University Fair"

    def test_channel_name_cannot_exceed_250_characters(self, channel_data):
        """Test that creating a channel with a name over 250 characters fails validation"""
        url = reverse("hrm:recruitment-channel-list")
        data = {
            **channel_data,
            "name": "N" * 251,
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.json()
        assert content["success"] is False
        assert "name" in content["error"]["errors"][0]["attr"]
        assert "250" in content["error"]["errors"][0]["detail"]

    def test_channel_description_allows_up_to_500_characters(self, channel_data):
        """Test that a 500 character description is accepted"""
        url = reverse("hrm:recruitment-channel-list")
        long_description = "D" * 500
        data = {
            **channel_data,
            "description": long_description,
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        channel = RecruitmentChannel.objects.first()
        assert channel.description == long_description

    def test_channel_description_cannot_exceed_500_characters(self, channel_data):
        """Test that descriptions longer than 500 characters are rejected"""
        url = reverse("hrm:recruitment-channel-list")
        data = {
            **channel_data,
            "description": "E" * 501,
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.json()
        assert content["success"] is False
        assert "description" == content["error"]["errors"][0]["attr"]
        assert "500" in content["error"]["errors"][0]["detail"]
