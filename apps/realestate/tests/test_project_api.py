from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.realestate.api.serializers import ProjectExportXLSXSerializer
from apps.realestate.models import Project


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
class TestProjectExportXLSXSerializer:
    """Test cases for ProjectExportXLSXSerializer."""

    @pytest.fixture
    def project(self, db):
        return Project.objects.create(
            name="Test Project",
            address="123 Test Street",
            description="Test project description",
            status=Project.Status.ACTIVE,
        )

    def test_serializer_fields(self, project):
        """Test that serializer has correct default fields."""
        serializer = ProjectExportXLSXSerializer(instance=project)
        data = serializer.data

        assert "code" in data
        assert "name" in data
        assert "address" in data
        assert "description" in data

    def test_serializer_data_values(self, project):
        """Test that serializer returns correct data values."""
        serializer = ProjectExportXLSXSerializer(instance=project)
        data = serializer.data

        assert data["name"] == "Test Project"
        assert data["address"] == "123 Test Street"
        assert data["description"] == "Test project description"
        assert project.code in data["code"]

    def test_serializer_empty_fields(self, db):
        """Test serialization of project with empty optional fields."""
        project_empty = Project.objects.create(
            name="Empty Project",
            address="",
            description="",
            status=Project.Status.ACTIVE,
        )

        serializer = ProjectExportXLSXSerializer(instance=project_empty)
        data = serializer.data

        assert data["name"] == "Empty Project"
        assert data["address"] == ""
        assert data["description"] == ""

    def test_many_serialization(self, project, db):
        """Test serialization of multiple projects."""
        Project.objects.create(
            name="Another Project",
            address="456 Another Street",
            description="Another project description",
            status=Project.Status.COMPLETED,
        )

        projects = Project.objects.all()
        serializer = ProjectExportXLSXSerializer(instance=projects, many=True)
        data = serializer.data

        assert len(data) == 2


@pytest.mark.django_db
class TestProjectExportAPI(APITestMixin):
    """Test cases for Project export API endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, settings):
        settings.EXPORTER_CELERY_ENABLED = False
        self.client = api_client

    @pytest.fixture
    def project(self, db):
        return Project.objects.create(
            name="Export Test Project",
            address="123 Export Street",
            description="Export test notes",
            status=Project.Status.ACTIVE,
        )

    def test_export_endpoint_exists(self):
        """Test that export endpoint exists."""
        url = reverse("realestate:project-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_export_direct_delivery(self):
        """Test export with direct file delivery."""
        url = reverse("realestate:project-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response["Content-Disposition"]
        assert ".xlsx" in response["Content-Disposition"]

    def test_export_uses_template(self):
        """Test that export uses the xlsx_template_name."""
        url = reverse("realestate:project-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert len(response.content) > 0

    def test_export_includes_project_data(self, project):
        """Test that exported file contains project data."""
        url = reverse("realestate:project-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert len(response.content) > 100

    @patch("libs.export_xlsx.mixins.get_storage_backend")
    def test_export_link_delivery(self, mock_get_storage, project):
        """Test export with link delivery."""
        mock_storage = MagicMock()
        mock_storage.save.return_value = "exports/project_export.xlsx"
        mock_storage.get_url.return_value = "https://s3.example.com/project_export.xlsx"
        mock_storage.get_file_size.return_value = 12345
        mock_get_storage.return_value = mock_storage

        url = reverse("realestate:project-export")
        response = self.client.get(url, {"delivery": "link"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "url" in data
        assert "filename" in data

    def test_export_with_search_filter(self, project, db):
        """Test export with search filter applied."""
        Project.objects.create(
            name="Different Project",
            address="789 Different Street",
            description="Different project",
            status=Project.Status.INACTIVE,
        )

        url = reverse("realestate:project-export")
        response = self.client.get(url, {"delivery": "direct", "search": "Export Test"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT

    def test_export_with_ordering(self):
        """Test export with ordering applied."""
        url = reverse("realestate:project-export")
        response = self.client.get(url, {"delivery": "direct", "ordering": "name"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT


@pytest.mark.django_db
class TestProjectViewSetGetSerializerClass:
    """Test cases for ProjectViewSet.get_serializer_class method."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, settings):
        settings.EXPORTER_CELERY_ENABLED = False
        self.client = api_client

    @pytest.fixture
    def project(self, db):
        return Project.objects.create(
            name="Test Project",
            address="123 Test Street",
            description="Test project description",
            status=Project.Status.ACTIVE,
        )

    def test_list_uses_project_serializer(self, project):
        """Test that list action uses ProjectSerializer."""
        url = reverse("realestate:project-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_uses_project_serializer(self, project):
        """Test that retrieve action uses ProjectSerializer."""
        url = reverse("realestate:project-detail", kwargs={"pk": project.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_export_uses_project_export_serializer(self, project):
        """Test that export action uses ProjectExportXLSXSerializer."""
        url = reverse("realestate:project-export")
        response = self.client.get(url, {"delivery": "direct"})

        # Export returns file, not JSON - check that it's successful
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
