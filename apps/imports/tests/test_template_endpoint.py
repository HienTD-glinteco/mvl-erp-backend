"""Tests for import template endpoint."""

from unittest.mock import PropertyMock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from apps.files.models import FileModel
from apps.imports.api.mixins import AsyncImportProgressMixin
from apps.imports.constants import FILE_PURPOSE_IMPORT_TEMPLATE
from apps.imports.models import ImportJob

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """Create authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def template_file(user):
    """Create a test template file."""
    return FileModel.objects.create(
        purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
        file_name="hrm_employees_template.csv",
        file_path="templates/imports/hrm_employees_template.csv",
        size=1024,
        is_confirmed=True,
        uploaded_by=user,
    )


@pytest.mark.django_db
class TestImportTemplateEndpoint:
    """Test cases for import_template endpoint."""

    @patch("apps.files.models.FileModel.download_url", new_callable=PropertyMock)
    def test_import_template_exists(self, mock_download_url, authenticated_client, template_file):
        """Test retrieving an existing template file."""
        # Mock the download_url property
        mock_download_url.return_value = "https://s3.example.com/template.csv?signature=abc123"

        # Create a mock ViewSet to test the mixin
        from rest_framework.viewsets import ModelViewSet

        class TestViewSet(AsyncImportProgressMixin, ModelViewSet):
            queryset = ImportJob.objects.all()

            def get_import_template_app_name(self):
                return "hrm"

        # Create ViewSet instance
        factory = APIRequestFactory()
        request = factory.get("/import_template/")
        request.user = authenticated_client.handler._force_user

        viewset = TestViewSet()
        viewset.request = request
        viewset.format_kwarg = None

        # Call the action
        response = viewset.import_template(request)

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert "file_id" in response.data
        assert "file_name" in response.data
        assert "download_url" in response.data
        assert response.data["file_id"] == template_file.id
        assert response.data["file_name"] == "hrm_employees_template.csv"

    def test_import_template_not_found(self, authenticated_client):
        """Test retrieving template when none exists."""
        from rest_framework.viewsets import ModelViewSet

        class TestViewSet(AsyncImportProgressMixin, ModelViewSet):
            queryset = ImportJob.objects.all()

            def get_import_template_app_name(self):
                return "nonexistent"

        # Create ViewSet instance
        factory = APIRequestFactory()
        request = factory.get("/import_template/")
        request.user = authenticated_client.handler._force_user

        viewset = TestViewSet()
        viewset.request = request
        viewset.format_kwarg = None

        # Call the action
        response = viewset.import_template(request)

        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.data

    def test_import_template_no_app_name(self, authenticated_client):
        """Test retrieving template when app name cannot be determined."""
        from rest_framework.viewsets import ModelViewSet

        class TestViewSet(AsyncImportProgressMixin, ModelViewSet):
            queryset = None  # No queryset to extract app name from

        # Create ViewSet instance
        factory = APIRequestFactory()
        request = factory.get("/import_template/")
        request.user = authenticated_client.handler._force_user

        viewset = TestViewSet()
        viewset.request = request
        viewset.format_kwarg = None

        # Call the action
        response = viewset.import_template(request)

        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.data

    @patch("apps.files.models.FileModel.download_url", new_callable=PropertyMock)
    def test_import_template_most_recent(self, mock_download_url, authenticated_client, user):
        """Test that the most recent template is returned."""
        # Mock the download_url property
        mock_download_url.return_value = "https://s3.example.com/template.csv?signature=abc123"

        # Create older template
        old_template = FileModel.objects.create(
            purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
            file_name="crm_customers_template.csv",
            file_path="templates/imports/crm_customers_template_old.csv",
            size=512,
            is_confirmed=True,
            uploaded_by=user,
        )

        # Create newer template
        new_template = FileModel.objects.create(
            purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
            file_name="crm_customers_template.csv",
            file_path="templates/imports/crm_customers_template_new.csv",
            size=1024,
            is_confirmed=True,
            uploaded_by=user,
        )

        from rest_framework.viewsets import ModelViewSet

        class TestViewSet(AsyncImportProgressMixin, ModelViewSet):
            queryset = ImportJob.objects.all()

            def get_import_template_app_name(self):
                return "crm"

        # Create ViewSet instance
        factory = APIRequestFactory()
        request = factory.get("/import_template/")
        request.user = authenticated_client.handler._force_user

        viewset = TestViewSet()
        viewset.request = request
        viewset.format_kwarg = None

        # Call the action
        response = viewset.import_template(request)

        # Verify that the newer template is returned
        assert response.status_code == status.HTTP_200_OK
        assert response.data["file_id"] == new_template.id

    def test_import_template_only_confirmed(self, authenticated_client, user):
        """Test that only confirmed templates are returned."""
        # Create unconfirmed template
        unconfirmed_template = FileModel.objects.create(
            purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
            file_name="core_users_template.csv",
            file_path="templates/imports/core_users_template.csv",
            size=512,
            is_confirmed=False,  # Not confirmed
            uploaded_by=user,
        )

        from rest_framework.viewsets import ModelViewSet

        class TestViewSet(AsyncImportProgressMixin, ModelViewSet):
            queryset = ImportJob.objects.all()

            def get_import_template_app_name(self):
                return "core"

        # Create ViewSet instance
        factory = APIRequestFactory()
        request = factory.get("/import_template/")
        request.user = authenticated_client.handler._force_user

        viewset = TestViewSet()
        viewset.request = request
        viewset.format_kwarg = None

        # Call the action
        response = viewset.import_template(request)

        # Verify that no template is found (unconfirmed should be ignored)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_import_template_app_name_from_queryset(self):
        """Test extracting app name from queryset model."""
        from rest_framework.viewsets import ModelViewSet

        class TestViewSet(AsyncImportProgressMixin, ModelViewSet):
            queryset = ImportJob.objects.all()

        viewset = TestViewSet()
        app_name = viewset.get_import_template_app_name()

        # ImportJob model is in the 'imports' app
        assert app_name == "imports"

    def test_get_import_template_app_name_custom_override(self):
        """Test custom override of app name."""
        from rest_framework.viewsets import ModelViewSet

        class TestViewSet(AsyncImportProgressMixin, ModelViewSet):
            queryset = None

            def get_import_template_app_name(self):
                return "custom_app"

        viewset = TestViewSet()
        app_name = viewset.get_import_template_app_name()

        assert app_name == "custom_app"
