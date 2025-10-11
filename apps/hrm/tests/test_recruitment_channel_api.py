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
            return content["data"]
        return content


class RecruitmentChannelAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Recruitment Channel API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        RecruitmentChannel.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
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
            {"name": "LinkedIn", "description": "Professional network"},
            format="json",
        )
        self.client.post(
            url,
            {"name": "Facebook Jobs", "description": "Social media jobs"},
            format="json",
        )
        self.client.post(
            url,
            {"name": "Indeed", "description": "Job search engine"},
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
            {"name": "Active Channel", "is_active": True},
            format="json",
        )
        self.client.post(
            url,
            {"name": "Inactive Channel", "is_active": False},
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
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-channel-list")
        response1 = self.client.post(url, {"name": "First Channel"}, format="json")
        response2 = self.client.post(url, {"name": "Second Channel"}, format="json")
        response3 = self.client.post(url, {"name": "Third Channel"}, format="json")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)
        # Most recent first
        self.assertEqual(response_data[0]["name"], "Third Channel")
        self.assertEqual(response_data[1]["name"], "Second Channel")
        self.assertEqual(response_data[2]["name"], "First Channel")
