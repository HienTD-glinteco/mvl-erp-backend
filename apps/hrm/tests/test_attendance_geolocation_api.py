import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import AttendanceGeolocation
from apps.realestate.models import Project

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class AttendanceGeolocationAPITest(TransactionTestCase, APITestMixin):
    """Test cases for AttendanceGeolocation API endpoints."""

    def setUp(self):
        # Clear all existing data for clean tests
        AttendanceGeolocation.objects.all().delete()
        Project.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test projects
        self.project1 = Project.objects.create(name="Main Office Project", code="DA001", status="active")
        self.project2 = Project.objects.create(name="Branch Office Project", code="DA002", status="active")

        # Create test geolocations
        self.geo1 = AttendanceGeolocation.objects.create(
            name="Headquarters Geofence",
            code="DV001",
            project=self.project1,
            address="123 Main Street, District 1, Ho Chi Minh City",
            latitude="10.7769000",
            longitude="106.7009000",
            radius_m=100,
            status="active",
            notes="Main office geofence area",
            created_by=self.user,
            updated_by=self.user,
        )
        self.geo2 = AttendanceGeolocation.objects.create(
            name="Branch Geofence",
            code="DV002",
            project=self.project2,
            address="456 Branch Road, District 2, Ho Chi Minh City",
            latitude="10.8000000",
            longitude="106.7200000",
            radius_m=150,
            status="active",
            notes="Branch office geofence",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_list_geolocations(self):
        """Test listing all project geolocations."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_retrieve_geolocation(self):
        """Test retrieving a single project geolocation."""
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": self.geo1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["code"], "DV001")
        self.assertEqual(data["name"], "Headquarters Geofence")
        self.assertEqual(data["radius_m"], 100)

    def test_create_geolocation(self):
        """Test creating a new project geolocation with auto-generated code."""
        url = reverse("hrm:attendance-geolocation-list")
        payload = {
            "name": "New Site Geofence",
            "project_id": self.project1.id,
            "address": "789 New Street, District 3, Ho Chi Minh City",
            "latitude": "10.7500000",
            "longitude": "106.6800000",
            "radius_m": 200,
            "status": "active",
            "notes": "New site geofence",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "New Site Geofence")
        self.assertTrue(data["code"].startswith("DV"))
        self.assertEqual(data["radius_m"], 200)

    def test_create_geolocation_missing_required_fields(self):
        """Test creating a geolocation with missing required fields."""
        url = reverse("hrm:attendance-geolocation-list")
        payload = {
            "name": "Incomplete Geofence",
            # Missing project_id, latitude, longitude
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_geolocation_invalid_radius(self):
        """Test creating a geolocation with invalid radius (< 1)."""
        url = reverse("hrm:attendance-geolocation-list")
        payload = {
            "name": "Invalid Radius Geofence",
            "project_id": self.project1.id,
            "latitude": "10.7500000",
            "longitude": "106.6800000",
            "radius_m": 0,  # Invalid: must be >= 1
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_geolocation(self):
        """Test updating a project geolocation."""
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": self.geo1.pk})
        payload = {
            "name": "Updated Headquarters Geofence",
            "project_id": self.project1.id,
            "address": "123 Main Street, District 1, Ho Chi Minh City",
            "latitude": "10.7769000",
            "longitude": "106.7009000",
            "radius_m": 250,
            "status": "active",
            "notes": "Updated geofence radius",
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "Updated Headquarters Geofence")
        self.assertEqual(data["radius_m"], 250)
        self.assertEqual(data["code"], "DV001")  # Code should remain unchanged

    def test_partial_update_geolocation(self):
        """Test partially updating a project geolocation."""
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": self.geo1.pk})
        payload = {
            "radius_m": 300,
            "notes": "Increased geofence radius",
        }
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["radius_m"], 300)
        self.assertEqual(data["notes"], "Increased geofence radius")

    def test_update_code_is_ignored(self):
        """Test that attempting to update code is ignored."""
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": self.geo1.pk})
        original_code = self.geo1.code
        payload = {
            "name": "Geofence with Code Update Attempt",
            "project_id": self.project1.id,
            "latitude": "10.7769000",
            "longitude": "106.7009000",
            "radius_m": 100,
            "code": "DV999",  # Attempt to change code
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["code"], original_code)  # Code should remain unchanged

    def test_soft_delete_geolocation(self):
        """Test soft-deleting a project geolocation."""
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": self.geo1.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify it's soft-deleted (deleted flag set to True)
        self.geo1.refresh_from_db()
        self.assertTrue(self.geo1.deleted)
        self.assertIsNotNone(self.geo1.deleted_at)

        # Verify it doesn't appear in list
        list_url = reverse("hrm:attendance-geolocation-list")
        list_response = self.client.get(list_url)
        data = self.get_response_data(list_response)
        self.assertEqual(len(data), 1)  # Only geo2 should be visible

    def test_search_geolocations_by_code(self):
        """Test searching geolocations by code (case-insensitive)."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"search": "dv001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["code"], "DV001")

    def test_search_geolocations_by_name(self):
        """Test searching geolocations by name (case-insensitive)."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"search": "headquarters"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Headquarters Geofence")

    def test_filter_geolocations_by_project(self):
        """Test filtering geolocations by project."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"project": self.project1.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["project"]["id"], self.project1.id)

    def test_filter_geolocations_by_status(self):
        """Test filtering geolocations by status."""
        # Create an inactive geolocation
        AttendanceGeolocation.objects.create(
            name="Inactive Geofence",
            code="DV003",
            project=self.project1,
            latitude="10.7000000",
            longitude="106.6000000",
            radius_m=100,
            status="inactive",
            created_by=self.user,
            updated_by=self.user,
        )

        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"status": "inactive"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "inactive")

    def test_ordering_geolocations_by_name(self):
        """Test ordering geolocations by name."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"ordering": "name"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data[0]["name"], "Branch Geofence")
        self.assertEqual(data[1]["name"], "Headquarters Geofence")

    def test_ordering_geolocations_by_created_at_desc(self):
        """Test ordering geolocations by created_at descending (default)."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        # Most recently created should be first
        self.assertEqual(data[0]["code"], "DV002")
