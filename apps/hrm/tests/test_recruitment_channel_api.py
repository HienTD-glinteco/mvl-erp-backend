import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import RecruitmentChannel

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


class RecruitmentChannelAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Recruitment Channel API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        RecruitmentChannel.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.channel_data = {
            "name": "LinkedIn",
            "belong_to": "job_website",
            "description": "Professional networking platform",
            "is_active": True,
        }

    def test_create_recruitment_channel(self):
        """Test creating a recruitment channel via API"""
        url = reverse("hrm:recruitment-channel-list")
        response = self.client.post(url, self.channel_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecruitmentChannel.objects.count(), 1)

        channel = RecruitmentChannel.objects.first()
        self.assertEqual(channel.name, self.channel_data["name"])
        self.assertEqual(channel.belong_to, self.channel_data["belong_to"])
        # Verify code was auto-generated
        self.assertTrue(channel.code.startswith("CH"))

    def test_list_recruitment_channels(self):
        """Test listing recruitment channels via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        self.client.post(url, self.channel_data, format="json")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], self.channel_data["name"])
        self.assertEqual(response_data[0]["belong_to"], self.channel_data["belong_to"])

    def test_retrieve_recruitment_channel(self):
        """Test retrieving a recruitment channel via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        create_response = self.client.post(url, self.channel_data, format="json")
        channel_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], self.channel_data["name"])

    def test_update_recruitment_channel(self):
        """Test updating a recruitment channel via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        create_response = self.client.post(url, self.channel_data, format="json")
        channel_id = self.get_response_data(create_response)["id"]

        update_data = {
            "name": "LinkedIn Updated",
            "belong_to": "marketing",
            "description": "Updated description",
            "is_active": True,
        }

        url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel_id})
        response = self.client.put(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        channel = RecruitmentChannel.objects.get(id=channel_id)
        self.assertEqual(channel.name, update_data["name"])
        self.assertEqual(channel.belong_to, update_data["belong_to"])
        self.assertEqual(channel.description, update_data["description"])

    def test_partial_update_recruitment_channel(self):
        """Test partially updating a recruitment channel via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        create_response = self.client.post(url, self.channel_data, format="json")
        channel_id = self.get_response_data(create_response)["id"]

        update_data = {"is_active": False}

        url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel_id})
        response = self.client.patch(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        channel = RecruitmentChannel.objects.get(id=channel_id)

        self.assertFalse(channel.is_active)
        # Belong_to should remain unchanged (default or previously set)

    def test_delete_recruitment_channel(self):
        """Test deleting a recruitment channel via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        create_response = self.client.post(url, self.channel_data, format="json")
        channel_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel_id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(RecruitmentChannel.objects.count(), 0)

    def test_search_recruitment_channels(self):
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "LinkedIn")

        # Search by code
        response = self.client.get(url, {"search": "CH"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # All channels should have CH prefix
        self.assertEqual(len(response_data), 3)

    def test_filter_recruitment_channels_by_active_status(self):
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Active Channel")

        # Filter inactive channels
        response = self.client.get(url, {"is_active": "false"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Inactive Channel")

    def test_unique_code_constraint(self):
        """Test that recruitment channel codes are auto-generated and unique"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        response1 = self.client.post(url, self.channel_data, format="json")
        response2 = self.client.post(url, self.channel_data, format="json")

        # Both should succeed with different codes
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

        data1 = self.get_response_data(response1)
        data2 = self.get_response_data(response2)
        self.assertNotEqual(data1["code"], data2["code"])

    def test_ordering_by_created_at_desc(self):
        """Test that channels are ordered by created_at descending by default"""
        url = reverse("hrm:recruitment-channel-list")
        self.client.post(url, {"name": "First Channel", "belong_to": "job_website"}, format="json")
        self.client.post(url, {"name": "Second Channel", "belong_to": "marketing"}, format="json")
        self.client.post(url, {"name": "Third Channel", "belong_to": "job_website"}, format="json")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)
        # Most recent first
        self.assertEqual(response_data[0]["name"], "Third Channel")
        self.assertEqual(response_data[1]["name"], "Second Channel")
        self.assertEqual(response_data[2]["name"], "First Channel")

    def test_create_channel_with_hunt_belong_to(self):
        """Test creating a recruitment channel with HUNT belong_to option"""
        url = reverse("hrm:recruitment-channel-list")
        channel_data = {
            "name": "LinkedIn Recruiter",
            "belong_to": "hunt",
            "description": "Headhunting via LinkedIn",
        }
        response = self.client.post(url, channel_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["belong_to"], "hunt")
        self.assertEqual(response_data["name"], "LinkedIn Recruiter")

    def test_create_channel_with_school_belong_to(self):
        """Test creating a recruitment channel with SCHOOL belong_to option"""
        url = reverse("hrm:recruitment-channel-list")
        channel_data = {
            "name": "University Job Fair",
            "belong_to": "school",
            "description": "Recruiting from universities",
        }
        response = self.client.post(url, channel_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["belong_to"], "school")
        self.assertEqual(response_data["name"], "University Job Fair")

    def test_filter_channels_by_belong_to(self):
        """Test filtering recruitment channels by belong_to option"""
        url = reverse("hrm:recruitment-channel-list")

        # Create channels with different belong_to values
        self.client.post(url, {"name": "Indeed", "belong_to": "job_website"}, format="json")
        self.client.post(url, {"name": "Facebook Ads", "belong_to": "marketing"}, format="json")
        self.client.post(url, {"name": "LinkedIn Recruiter", "belong_to": "hunt"}, format="json")
        self.client.post(url, {"name": "University Fair", "belong_to": "school"}, format="json")

        # Filter by hunt
        response = self.client.get(url, {"belong_to": "hunt"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "LinkedIn Recruiter")

        # Filter by school
        response = self.client.get(url, {"belong_to": "school"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "University Fair")

    def test_channel_name_cannot_exceed_250_characters(self):
        """Test that creating a channel with a name over 250 characters fails validation"""
        url = reverse("hrm:recruitment-channel-list")
        data = {
            **self.channel_data,
            "name": "N" * 251,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertFalse(content["success"])
        self.assertIn("name", content["error"]["errors"][0]["attr"])
        self.assertIn("250", content["error"]["errors"][0]["detail"])

    def test_channel_description_allows_up_to_500_characters(self):
        """Test that a 500 character description is accepted"""
        url = reverse("hrm:recruitment-channel-list")
        long_description = "D" * 500
        data = {
            **self.channel_data,
            "description": long_description,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        channel = RecruitmentChannel.objects.first()
        self.assertEqual(channel.description, long_description)

    def test_channel_description_cannot_exceed_500_characters(self):
        """Test that descriptions longer than 500 characters are rejected"""
        url = reverse("hrm:recruitment-channel-list")
        data = {
            **self.channel_data,
            "description": "E" * 501,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertFalse(content["success"])
        self.assertEqual("description", content["error"]["errors"][0]["attr"])
        self.assertIn("500", content["error"]["errors"][0]["detail"])
