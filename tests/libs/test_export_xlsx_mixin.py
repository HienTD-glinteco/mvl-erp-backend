"""
Tests for ExportXLSXMixin.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.core.models import Role
from libs.export_xlsx import ExportXLSXMixin
from libs.base_viewset import BaseModelViewSet

User = get_user_model()


class TestExportViewSet(ExportXLSXMixin, BaseModelViewSet):
    """Test ViewSet with export mixin."""

    queryset = Role.objects.all()
    serializer_class = None  # Not needed for export tests


@override_settings(EXPORTER_CELERY_ENABLED=False)
class ExportXLSXMixinTests(TestCase):
    """Test cases for ExportXLSXMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

        # Create test data
        Role.objects.create(code="admin", name="Administrator")
        Role.objects.create(code="user", name="User")

    def test_export_action_exists(self):
        """Test that export action exists."""
        viewset = TestExportViewSet()
        self.assertTrue(hasattr(viewset, "export"))

    def test_synchronous_export(self):
        """Test synchronous export returns file."""
        request = self.factory.get("/api/test/export/")
        request.user = self.user

        viewset = TestExportViewSet()
        viewset.request = request
        viewset.format_kwarg = None

        # Mock filter_queryset and get_queryset
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])

    @override_settings(EXPORTER_CELERY_ENABLED=True)
    @patch("libs.export_xlsx.mixins.generate_xlsx_task.delay")
    def test_async_export_with_celery_enabled(self, mock_task):
        """Test async export when Celery is enabled."""
        mock_task.return_value.id = "test-task-id-123"

        request = self.factory.get("/api/test/export/?async=true")
        request.user = self.user

        viewset = TestExportViewSet()
        viewset.request = request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["task_id"], "test-task-id-123")
        self.assertEqual(response.data["status"], "PENDING")
        self.assertTrue(mock_task.called)

    def test_async_export_without_celery_enabled(self):
        """Test async export fails when Celery is not enabled."""
        request = self.factory.get("/api/test/export/?async=true")
        request.user = self.user

        viewset = TestExportViewSet()
        viewset.request = request
        viewset.format_kwarg = None

        response = viewset.export(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_export_data_default(self):
        """Test default export data generation."""
        request = self.factory.get("/api/test/export/")
        request.user = self.user

        viewset = TestExportViewSet()
        viewset.request = request
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        schema = viewset.get_export_data(request)

        self.assertIn("sheets", schema)
        self.assertEqual(len(schema["sheets"]), 1)

        sheet = schema["sheets"][0]
        self.assertIn("headers", sheet)
        self.assertIn("data", sheet)
        self.assertEqual(len(sheet["data"]), 2)  # We created 2 roles

    def test_custom_get_export_data(self):
        """Test custom export data generation."""

        class CustomExportViewSet(ExportXLSXMixin, BaseModelViewSet):
            queryset = Role.objects.all()
            serializer_class = None

            def get_export_data(self, request):
                return {
                    "sheets": [
                        {
                            "name": "Custom Sheet",
                            "headers": ["Code", "Name"],
                            "data": [
                                {"code": "admin", "name": "Administrator"},
                            ],
                        }
                    ]
                }

        request = self.factory.get("/api/test/export/")
        request.user = self.user

        viewset = CustomExportViewSet()
        viewset.request = request

        schema = viewset.get_export_data(request)

        self.assertEqual(schema["sheets"][0]["name"], "Custom Sheet")
        self.assertEqual(len(schema["sheets"][0]["data"]), 1)

    def test_get_export_filename(self):
        """Test export filename generation."""
        viewset = TestExportViewSet()
        filename = viewset._get_export_filename()

        self.assertTrue(filename.endswith(".xlsx"))
        self.assertIn("role", filename.lower())  # Should include model name
