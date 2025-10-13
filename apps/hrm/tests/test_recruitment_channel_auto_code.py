"""Tests for RecruitmentChannel API auto-code generation."""

import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import RecruitmentChannel

User = get_user_model()


class RecruitmentChannelAutoCodeGenerationAPITest(TransactionTestCase):
    """Test cases for RecruitmentChannel API auto-code generation."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        RecruitmentChannel.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def test_create_channel_without_code_auto_generates(self):
        """Test creating a recruitment channel without code field auto-generates code."""
        # Arrange
        channel_data = {
            "name": "LinkedIn",
            "belong_to": "job_website",
            "description": "Professional networking platform",
        }

        # Act
        url = reverse("hrm:recruitment-channel-list")
        response = self.client.post(url, channel_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        self.assertIn("code", response_data)
        self.assertTrue(response_data["code"].startswith("CH"))

        # Verify in database
        channel = RecruitmentChannel.objects.first()
        self.assertIsNotNone(channel)
        self.assertEqual(channel.code, response_data["code"])

    def test_create_channel_with_code_ignores_provided_code(self):
        """Test that provided code is ignored and auto-generated code is used."""
        # Arrange
        channel_data = {
            "name": "LinkedIn",
            "code": "MANUAL",  # This should be ignored
            "belong_to": "job_website",
            "description": "Professional networking platform",
        }

        # Act
        url = reverse("hrm:recruitment-channel-list")
        response = self.client.post(url, channel_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify auto-generated code was used, not manual code
        self.assertNotEqual(response_data["code"], "MANUAL")
        self.assertTrue(response_data["code"].startswith("CH"))

    def test_auto_generated_code_format_single_digit(self):
        """Test auto-generated code format for first channel (CH001)."""
        # Arrange
        channel_data = {
            "name": "LinkedIn",
            "belong_to": "job_website",
        }

        # Act
        url = reverse("hrm:recruitment-channel-list")
        response = self.client.post(url, channel_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code format (should be at least 3 digits)
        channel = RecruitmentChannel.objects.first()
        self.assertEqual(channel.code, f"CH{channel.id:03d}")

    def test_auto_generated_code_multiple_channels(self):
        """Test auto-generated codes for multiple channels."""
        # Arrange
        url = reverse("hrm:recruitment-channel-list")

        # Act - Create 3 channels
        for i in range(3):
            channel_data = {
                "name": f"Channel {i + 1}",
                "belong_to": "marketing" if i % 2 else "job_website",
            }
            response = self.client.post(url, channel_data, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Assert - Verify all channels have unique auto-generated codes
        channels = RecruitmentChannel.objects.all().order_by("id")
        self.assertEqual(channels.count(), 3)

        codes = [channel.code for channel in channels]
        # All codes should be unique
        self.assertEqual(len(codes), len(set(codes)))
        # All codes should start with CH
        for code in codes:
            self.assertTrue(code.startswith("CH"))

    def test_code_field_is_readonly_in_response(self):
        """Test that code field is included in response but not writable."""
        # Arrange
        channel_data = {
            "name": "LinkedIn",
            "belong_to": "job_website",
        }

        # Act - Create channel
        url = reverse("hrm:recruitment-channel-list")
        response = self.client.post(url, channel_data, format="json")

        # Assert - Response includes code
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertIn("code", response_data)
        original_code = response_data["code"]

        # Act - Try to update code
        channel = RecruitmentChannel.objects.first()
        update_url = reverse("hrm:recruitment-channel-detail", kwargs={"pk": channel.pk})
        update_data = {"code": "NEWCODE"}
        update_response = self.client.patch(update_url, update_data, format="json")

        # Assert - Code should not be updated
        channel.refresh_from_db()
        self.assertNotEqual(channel.code, "NEWCODE")
        self.assertEqual(channel.code, original_code)

    def test_channel_with_description(self):
        """Test creating a channel with description field."""
        # Arrange
        channel_data = {
            "name": "LinkedIn",
            "belong_to": "job_website",
            "description": "Professional networking platform",
        }

        # Act
        url = reverse("hrm:recruitment-channel-list")
        response = self.client.post(url, channel_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["description"], channel_data["description"])

        # Verify in database
        channel = RecruitmentChannel.objects.first()
        self.assertEqual(channel.description, channel_data["description"])
