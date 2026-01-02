import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import AttendanceGeolocation
from apps.realestate.models import Project

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestAttendanceGeolocationAPI(APITestMixin):
    """Test cases for AttendanceGeolocation API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser):
        self.user = superuser
        self.client = api_client

    @pytest.fixture
    def projects(self):
        project1 = Project.objects.create(name="Main Office Project", code="DA001", status="active")
        project2 = Project.objects.create(name="Branch Office Project", code="DA002", status="active")
        return project1, project2

    @pytest.fixture
    def geolocations(self, projects):
        project1, project2 = projects
        geo1 = AttendanceGeolocation.objects.create(
            name="Headquarters Geofence",
            code="DV001",
            project=project1,
            address="123 Main Street, District 1, Ho Chi Minh City",
            latitude="10.7769000",
            longitude="106.7009000",
            radius_m=100,
            status="active",
            notes="Main office geofence area",
            created_by=self.user,
            updated_by=self.user,
        )
        geo2 = AttendanceGeolocation.objects.create(
            name="Branch Geofence",
            code="DV002",
            project=project2,
            address="456 Branch Road, District 2, Ho Chi Minh City",
            latitude="10.8000000",
            longitude="106.7200000",
            radius_m=150,
            status="active",
            notes="Branch office geofence",
            created_by=self.user,
            updated_by=self.user,
        )
        return geo1, geo2

    def test_list_geolocations(self, geolocations):
        """Test listing all project geolocations."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_retrieve_geolocation(self, geolocations):
        """Test retrieving a single project geolocation."""
        geo1, _ = geolocations
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": geo1.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["code"] == "DV001"
        assert data["name"] == "Headquarters Geofence"
        assert data["radius_m"] == 100

    def test_create_geolocation(self, projects):
        """Test creating a new project geolocation with auto-generated code."""
        project1, _ = projects
        url = reverse("hrm:attendance-geolocation-list")
        payload = {
            "name": "New Site Geofence",
            "project_id": project1.id,
            "address": "789 New Street, District 3, Ho Chi Minh City",
            "latitude": "10.7500000",
            "longitude": "106.6800000",
            "radius_m": 200,
            "status": "active",
            "notes": "New site geofence",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        assert data["name"] == "New Site Geofence"
        assert data["code"].startswith("DV")
        assert data["radius_m"] == 200

    def test_create_geolocation_missing_required_fields(self):
        """Test creating a geolocation with missing required fields."""
        url = reverse("hrm:attendance-geolocation-list")
        payload = {
            "name": "Incomplete Geofence",
            # Missing project_id, latitude, longitude
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_geolocation_invalid_radius(self, projects):
        """Test creating a geolocation with invalid radius (< 1)."""
        project1, _ = projects
        url = reverse("hrm:attendance-geolocation-list")
        payload = {
            "name": "Invalid Radius Geofence",
            "project_id": project1.id,
            "latitude": "10.7500000",
            "longitude": "106.6800000",
            "radius_m": 0,  # Invalid: must be >= 1
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_geolocation(self, geolocations, projects):
        """Test updating a project geolocation."""
        geo1, _ = geolocations
        project1, _ = projects
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": geo1.pk})
        payload = {
            "name": "Updated Headquarters Geofence",
            "project_id": project1.id,
            "address": "123 Main Street, District 1, Ho Chi Minh City",
            "latitude": "10.7769000",
            "longitude": "106.7009000",
            "radius_m": 250,
            "status": "active",
            "notes": "Updated geofence radius",
        }
        response = self.client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["name"] == "Updated Headquarters Geofence"
        assert data["radius_m"] == 250
        assert data["code"] == "DV001"  # Code should remain unchanged

    def test_partial_update_geolocation(self, geolocations):
        """Test partially updating a project geolocation."""
        geo1, _ = geolocations
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": geo1.pk})
        payload = {
            "radius_m": 300,
            "notes": "Increased geofence radius",
        }
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["radius_m"] == 300
        assert data["notes"] == "Increased geofence radius"

    def test_update_code_is_ignored(self, geolocations, projects):
        """Test that attempting to update code is ignored."""
        geo1, _ = geolocations
        project1, _ = projects
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": geo1.pk})
        original_code = geo1.code
        payload = {
            "name": "Geofence with Code Update Attempt",
            "project_id": project1.id,
            "latitude": "10.7769000",
            "longitude": "106.7009000",
            "radius_m": 100,
            "code": "DV999",  # Attempt to change code
        }
        response = self.client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["code"] == original_code  # Code should remain unchanged

    def test_soft_delete_geolocation(self, geolocations):
        """Test soft-deleting a project geolocation."""
        geo1, geo2 = geolocations
        url = reverse("hrm:attendance-geolocation-detail", kwargs={"pk": geo1.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's soft-deleted
        geo1.refresh_from_db()
        assert geo1.deleted is True
        assert geo1.deleted_at is not None

        # Verify it doesn't appear in list
        list_url = reverse("hrm:attendance-geolocation-list")
        list_response = self.client.get(list_url)
        data = self.get_response_data(list_response)
        assert len(data) == 1  # Only geo2 should be visible

    def test_search_geolocations_by_code(self, geolocations):
        """Test searching geolocations by code (case-insensitive)."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"search": "dv001"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["code"] == "DV001"

    def test_search_geolocations_by_name(self, geolocations):
        """Test searching geolocations by name (case-insensitive)."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"search": "headquarters"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["name"] == "Headquarters Geofence"

    def test_filter_geolocations_by_project(self, geolocations, projects):
        """Test filtering geolocations by project."""
        project1, _ = projects
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"project": project1.id})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["project"]["id"] == project1.id

    def test_filter_geolocations_by_status(self, geolocations, projects):
        """Test filtering geolocations by status."""
        project1, _ = projects
        # Create an inactive geolocation
        AttendanceGeolocation.objects.create(
            name="Inactive Geofence",
            code="DV003",
            project=project1,
            latitude="10.7000000",
            longitude="106.6000000",
            radius_m=100,
            status="inactive",
            created_by=self.user,
            updated_by=self.user,
        )

        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"status": "inactive"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["status"] == "inactive"

    def test_ordering_geolocations_by_name(self, geolocations):
        """Test ordering geolocations by name."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url, {"ordering": "name"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data[0]["name"] == "Branch Geofence"
        assert data[1]["name"] == "Headquarters Geofence"

    def test_ordering_geolocations_by_created_at_desc(self, geolocations):
        """Test ordering geolocations by created_at descending (default)."""
        url = reverse("hrm:attendance-geolocation-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        # Most recently created should be first
        assert data[0]["code"] == "DV002"
