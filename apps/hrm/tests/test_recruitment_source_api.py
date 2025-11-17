import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import RecruitmentSource

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


class RecruitmentSourceAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Recruitment Source API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        RecruitmentSource.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.source_data = {
            "name": "Employee Referral",
            "description": "Candidates referred by current employees",
        }

    def test_create_recruitment_source(self):
        """Test creating a recruitment source via API"""
        url = reverse("hrm:recruitment-source-list")
        response = self.client.post(url, self.source_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecruitmentSource.objects.count(), 1)

        source = RecruitmentSource.objects.first()
        self.assertEqual(source.name, self.source_data["name"])
        self.assertEqual(source.description, self.source_data["description"])
        # Verify code was auto-generated
        self.assertTrue(source.code.startswith("RS"))

    def test_list_recruitment_sources(self):
        """Test listing recruitment sources via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        self.client.post(url, self.source_data, format="json")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], self.source_data["name"])
        self.assertEqual(response_data[0]["description"], self.source_data["description"])

    def test_retrieve_recruitment_source(self):
        """Test retrieving a recruitment source via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        create_response = self.client.post(url, self.source_data, format="json")
        source_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-source-detail", kwargs={"pk": source_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], self.source_data["name"])

    def test_update_recruitment_source(self):
        """Test updating a recruitment source via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        create_response = self.client.post(url, self.source_data, format="json")
        source_id = self.get_response_data(create_response)["id"]

        update_data = {
            "name": "Employee Referral Updated",
            "description": "Updated description for employee referrals",
        }

        url = reverse("hrm:recruitment-source-detail", kwargs={"pk": source_id})
        response = self.client.put(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        source = RecruitmentSource.objects.get(id=source_id)
        self.assertEqual(source.name, update_data["name"])
        self.assertEqual(source.description, update_data["description"])

    def test_partial_update_recruitment_source(self):
        """Test partially updating a recruitment source via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        create_response = self.client.post(url, self.source_data, format="json")
        source_id = self.get_response_data(create_response)["id"]

        update_data = {"description": "Partially updated description"}

        url = reverse("hrm:recruitment-source-detail", kwargs={"pk": source_id})
        response = self.client.patch(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        source = RecruitmentSource.objects.get(id=source_id)

        self.assertEqual(source.description, update_data["description"])
        # Name should remain unchanged
        self.assertEqual(source.name, self.source_data["name"])

    def test_delete_recruitment_source(self):
        """Test deleting a recruitment source via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        create_response = self.client.post(url, self.source_data, format="json")
        source_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-source-detail", kwargs={"pk": source_id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(RecruitmentSource.objects.count(), 0)

    def test_search_recruitment_sources(self):
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Employee Referral")

        # Search by code
        response = self.client.get(url, {"search": "RS"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # All sources should have RS prefix
        self.assertEqual(len(response_data), 3)

    def test_unique_code_constraint(self):
        """Test that recruitment source codes are auto-generated and unique"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:recruitment-source-list")
        response1 = self.client.post(url, self.source_data, format="json")
        response2 = self.client.post(url, self.source_data, format="json")

        # Both should succeed with different codes
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

        data1 = self.get_response_data(response1)
        data2 = self.get_response_data(response2)
        self.assertNotEqual(data1["code"], data2["code"])

    def test_ordering_by_created_at_desc(self):
        """Test that sources are ordered by created_at descending by default"""
        url = reverse("hrm:recruitment-source-list")
        self.client.post(url, {"name": "First Source"}, format="json")
        self.client.post(url, {"name": "Second Source"}, format="json")
        self.client.post(url, {"name": "Third Source"}, format="json")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)
        # Most recent first
        self.assertEqual(response_data[0]["name"], "Third Source")
        self.assertEqual(response_data[1]["name"], "Second Source")
        self.assertEqual(response_data[2]["name"], "First Source")

    def test_filter_by_name(self):
        """Test filtering recruitment sources by name"""
        url = reverse("hrm:recruitment-source-list")
        self.client.post(url, {"name": "Employee Referral"}, format="json")
        self.client.post(url, {"name": "Job Fair"}, format="json")
        self.client.post(url, {"name": "Campus Recruitment"}, format="json")

        # Filter by name containing "Referral"
        response = self.client.get(url, {"name": "Referral"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Employee Referral")

    def test_empty_description_allowed(self):
        """Test that description field can be empty"""
        url = reverse("hrm:recruitment-source-list")
        data = {"name": "Walk-in"}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        source = RecruitmentSource.objects.first()
        self.assertEqual(source.name, data["name"])
        self.assertEqual(source.description, "")

    def test_allow_referral_defaults_to_false(self):
        """Test that allow_referral field defaults to False"""
        # Arrange: Create a recruitment source without specifying allow_referral
        url = reverse("hrm:recruitment-source-list")
        data = {"name": "Job Board", "description": "Online job board"}

        # Act: Create the source via API
        response = self.client.post(url, data, format="json")

        # Assert: Check that allow_referral is False by default
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        source = RecruitmentSource.objects.first()
        self.assertFalse(source.allow_referral)

        # Assert: Verify it's in the serialized response
        response_data = self.get_response_data(response)
        self.assertIn("allow_referral", response_data)
        self.assertFalse(response_data["allow_referral"])

    def test_allow_referral_can_be_set_to_true(self):
        """Test that allow_referral field can be set to True"""
        # Arrange: Prepare data with allow_referral=True
        url = reverse("hrm:recruitment-source-list")
        data = {"name": "Employee Referral", "description": "Referred by employees", "allow_referral": True}

        # Act: Create the source via API
        response = self.client.post(url, data, format="json")

        # Assert: Check that allow_referral is True
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        source = RecruitmentSource.objects.first()
        self.assertTrue(source.allow_referral)

        # Assert: Verify it's in the serialized response
        response_data = self.get_response_data(response)
        self.assertTrue(response_data["allow_referral"])

    def test_allow_referral_can_be_set_to_false_explicitly(self):
        """Test that allow_referral field can be set to False explicitly"""
        # Arrange: Prepare data with allow_referral=False
        url = reverse("hrm:recruitment-source-list")
        data = {"name": "Walk-in", "description": "Walk-in candidates", "allow_referral": False}

        # Act: Create the source via API
        response = self.client.post(url, data, format="json")

        # Assert: Check that allow_referral is False
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        source = RecruitmentSource.objects.first()
        self.assertFalse(source.allow_referral)

        # Assert: Verify it's in the serialized response
        response_data = self.get_response_data(response)
        self.assertFalse(response_data["allow_referral"])

    def test_allow_referral_api_serialization(self):
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
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)

        # Assert: Verify the first source has allow_referral=False (most recent first)
        self.assertIn("allow_referral", response_data[0])
        self.assertFalse(response_data[0]["allow_referral"])

        # Assert: Verify the second source has allow_referral=True
        self.assertIn("allow_referral", response_data[1])
        self.assertTrue(response_data[1]["allow_referral"])
