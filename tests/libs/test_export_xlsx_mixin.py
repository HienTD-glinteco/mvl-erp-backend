"""
Tests for ExportXLSXMixin.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.core.models import Role
from libs.drf.base_viewset import BaseModelViewSet
from libs.export_xlsx import ExportXLSXMixin

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

    @override_settings(EXPORTER_DEFAULT_DELIVERY="direct")
    def test_synchronous_export_direct_default(self):
        """Test synchronous export returns file when default is direct."""
        request = self.factory.get("/api/test/export/")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None

        # Mock filter_queryset and get_queryset
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])

    def test_synchronous_export_direct_explicit(self):
        """Test synchronous export with delivery=direct returns file."""
        request = self.factory.get("/api/test/export/?delivery=direct")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None

        # Mock filter_queryset and get_queryset
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])

    def test_invalid_delivery_parameter(self):
        """Test that invalid delivery parameter returns 400."""
        request = self.factory.get("/api/test/export/?delivery=invalid")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    @patch("libs.export_xlsx.mixins.get_storage_backend")
    def test_synchronous_export_link_delivery(self, mock_get_storage):
        """Test synchronous export with Link delivery returns presigned URL."""
        # Mock S3 storage backend
        mock_storage = MagicMock()
        mock_storage.save.return_value = "exports/20250101_120000_roles_export.xlsx"
        mock_storage.get_url.return_value = "https://s3.amazonaws.com/bucket/file.xlsx?signature=abc123"
        mock_storage.get_file_size.return_value = 12345
        mock_get_storage.return_value = mock_storage

        request = self.factory.get("/api/test/export/?delivery=link")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("url", response.data)
        self.assertIn("filename", response.data)
        self.assertIn("expires_in", response.data)
        self.assertIn("storage_backend", response.data)
        self.assertEqual(response.data["storage_backend"], "s3")
        self.assertIn("size_bytes", response.data)
        self.assertEqual(response.data["size_bytes"], 12345)

    @patch("libs.export_xlsx.mixins.get_storage_backend")
    def test_synchronous_export_link_default(self, mock_get_storage):
        """Test synchronous export defaults to Link delivery."""
        # Mock S3 storage backend
        mock_storage = MagicMock()
        mock_storage.save.return_value = "exports/20250101_120000_roles_export.xlsx"
        mock_storage.get_url.return_value = "https://s3.amazonaws.com/bucket/file.xlsx?signature=abc123"
        mock_storage.get_file_size.return_value = 12345
        mock_get_storage.return_value = mock_storage

        request = self.factory.get("/api/test/export/")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("url", response.data)
        self.assertEqual(response.data["storage_backend"], "s3")

    @patch("libs.export_xlsx.mixins.get_storage_backend")
    def test_link_delivery_link_alias(self, mock_get_storage):
        """Test that 'link' alias works for Link delivery."""
        # Mock S3 storage backend
        mock_storage = MagicMock()
        mock_storage.save.return_value = "exports/20250101_120000_roles_export.xlsx"
        mock_storage.get_url.return_value = "https://s3.amazonaws.com/bucket/file.xlsx?signature=abc123"
        mock_storage.get_file_size.return_value = 12345
        mock_get_storage.return_value = mock_storage

        request = self.factory.get("/api/test/export/?delivery=link")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("url", response.data)

    @patch("libs.export_xlsx.mixins.get_storage_backend")
    def test_link_delivery_upload_error(self, mock_get_storage):
        """Test Link delivery handles upload errors gracefully."""
        # Mock S3 storage backend that raises an error
        mock_storage = MagicMock()
        mock_storage.save.side_effect = Exception("S3 upload failed")
        mock_get_storage.return_value = mock_storage

        request = self.factory.get("/api/test/export/?delivery=link")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)

    @override_settings(EXPORTER_CELERY_ENABLED=True)
    @patch("libs.export_xlsx.mixins.generate_xlsx_from_queryset_task.delay")
    def test_async_export_with_celery_enabled(self, mock_task):
        """Test async export when Celery is enabled."""
        mock_task.return_value.id = "test-task-id-123"

        request = self.factory.get("/api/test/export/?async=true")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["task_id"], "test-task-id-123")
        self.assertEqual(response.data["status"], "PENDING")
        self.assertTrue(mock_task.called)

    @override_settings(EXPORTER_CELERY_ENABLED=True, EXPORTER_STORAGE_BACKEND="s3")
    @patch("libs.export_xlsx.mixins.generate_xlsx_from_queryset_task.delay")
    def test_async_export_respects_storage_backend_setting(self, mock_task):
        """Test async export uses configured storage backend."""
        mock_task.return_value.id = "test-task-id-456"

        request = self.factory.get("/api/test/export/?async=true")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        # Verify storage_backend was passed to task
        call_args = mock_task.call_args
        self.assertEqual(call_args[1]["storage_backend"], "s3")

    @override_settings(EXPORTER_CELERY_ENABLED=True)
    @patch("libs.export_xlsx.mixins.generate_xlsx_from_queryset_task.delay")
    def test_async_export_with_delivery_link(self, mock_task):
        """Test async export with delivery=link uses S3 backend."""
        mock_task.return_value.id = "test-task-id-789"

        request = self.factory.get("/api/test/export/?async=true&delivery=link")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        # Verify S3 storage_backend was passed to task
        call_args = mock_task.call_args
        self.assertEqual(call_args[1]["storage_backend"], "s3")

    @override_settings(EXPORTER_CELERY_ENABLED=True)
    @patch("libs.export_xlsx.mixins.generate_xlsx_from_queryset_task.delay")
    def test_async_export_with_delivery_direct(self, mock_task):
        """Test async export with delivery=direct uses local backend."""
        mock_task.return_value.id = "test-task-id-012"

        request = self.factory.get("/api/test/export/?async=true&delivery=direct")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        # Verify local storage_backend was passed to task
        call_args = mock_task.call_args
        self.assertEqual(call_args[1]["storage_backend"], "local")

    def test_async_export_without_celery_enabled(self):
        """Test async export fails when Celery is not enabled."""
        request = self.factory.get("/api/test/export/?async=true")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None

        response = viewset.export(drf_request)

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

    @override_settings(EXPORTER_CELERY_ENABLED=True)
    @patch("libs.export_xlsx.mixins.generate_xlsx_from_viewset_task.delay")
    def test_async_export_with_custom_schema(self, mock_task):
        """Test async export with custom get_export_data uses ViewSet task."""

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

        mock_task.return_value.id = "test-task-custom-123"

        request = self.factory.get("/api/test/export/?async=true")
        request.user = self.user
        drf_request = Request(request)

        viewset = CustomExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["task_id"], "test-task-custom-123")
        self.assertEqual(response.data["status"], "PENDING")
        self.assertTrue(mock_task.called)
        # Verify it was called with ViewSet path
        call_args = mock_task.call_args
        self.assertIn("viewset_class_path", call_args[1])

    @override_settings(EXPORTER_PRESIGNED_URL_EXPIRES=7200)
    @patch("libs.export_xlsx.mixins.get_storage_backend")
    def test_link_delivery_custom_expiration(self, mock_get_storage):
        """Test Link delivery respects custom expiration setting."""
        # Mock S3 storage backend
        mock_storage = MagicMock()
        mock_storage.save.return_value = "exports/20250101_120000_roles_export.xlsx"
        mock_storage.get_url.return_value = "https://s3.amazonaws.com/bucket/file.xlsx?signature=abc123"
        mock_storage.get_file_size.return_value = 12345
        mock_get_storage.return_value = mock_storage

        request = self.factory.get("/api/test/export/?delivery=link")
        request.user = self.user
        drf_request = Request(request)

        viewset = TestExportViewSet()
        viewset.request = drf_request
        viewset.format_kwarg = None
        viewset.filter_queryset = lambda qs: qs
        viewset.get_queryset = lambda: Role.objects.all()

        response = viewset.export(drf_request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["expires_in"], 7200)
