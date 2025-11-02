"""
Tests for ExportDocumentMixin functionality.
"""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import JobDescription
from libs.export_document.constants import (
    ERROR_INVALID_DELIVERY,
    ERROR_INVALID_FILE_TYPE,
)

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.integration
class TestExportDocumentMixin:
    """Test ExportDocumentMixin integration with ViewSets"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        # Create test user
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            position_title="Senior Backend Developer",
            responsibility="Develop and maintain backend services",
            requirement="5+ years Python experience",
            preferred_criteria="Experience with Django and FastAPI",
            benefit="Competitive salary and benefits",
            proposed_salary="2000-3000 USD",
            note="Remote work available",
        )

    def test_export_document_pdf_direct_delivery(self):
        """Test exporting document as PDF with direct delivery"""
        # Arrange
        url = reverse("hrm:job-description-export-detail-document", kwargs={"pk": self.job_description.pk})

        # Act
        response = self.client.get(url, {"type": "pdf", "delivery": "direct"})

        # Assert
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/pdf"
        assert "attachment" in response["Content-Disposition"]
        # Filename uses underscores, not hyphens (slugify converts spaces to hyphens, but preserves underscores)
        assert f"job_description_{self.job_description.code}".lower() in response["Content-Disposition"].lower()
        # Verify it's a PDF
        assert response.content[:4] == b"%PDF"

    @patch("libs.export_document.mixins.convert_html_to_docx")
    def test_export_document_docx_direct_delivery(self, mock_convert):
        """Test exporting document as DOCX with direct delivery"""
        # Arrange
        # Create a real temporary file
        tmp_file = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        tmp_file.write(b"fake docx content")
        tmp_file.close()

        mock_convert.return_value = {
            "file_path": tmp_file.name,
            "file_name": f"job_description_{self.job_description.code}.docx",
            "size": 18,
        }
        url = reverse("hrm:job-description-export-detail-document", kwargs={"pk": self.job_description.pk})

        try:
            # Act
            response = self.client.get(url, {"type": "docx", "delivery": "direct"})

            # Assert
            assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
            assert (
                response["Content-Type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            assert "attachment" in response["Content-Disposition"]
            mock_convert.assert_called_once()
        finally:
            # Clean up
            if os.path.exists(tmp_file.name):
                os.unlink(tmp_file.name)

    def test_export_document_default_parameters(self):
        """Test exporting document with default parameters (PDF, direct)"""
        # Arrange
        url = reverse("hrm:job-description-export-detail-document", kwargs={"pk": self.job_description.pk})

        # Act
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/pdf"

    def test_export_document_invalid_file_type(self):
        """Test exporting document with invalid file type"""
        # Arrange
        url = reverse("hrm:job-description-export-detail-document", kwargs={"pk": self.job_description.pk})

        # Act
        response = self.client.get(url, {"type": "txt"})

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(response.content.decode())
        # Response is wrapped by ApiResponseWrapperMiddleware
        assert content["success"] is False
        assert ERROR_INVALID_FILE_TYPE in content["error"]["error"]

    def test_export_document_invalid_delivery_mode(self):
        """Test exporting document with invalid delivery mode"""
        # Arrange
        url = reverse("hrm:job-description-export-detail-document", kwargs={"pk": self.job_description.pk})

        # Act
        response = self.client.get(url, {"delivery": "email"})

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(response.content.decode())
        # Response is wrapped by ApiResponseWrapperMiddleware
        assert content["success"] is False
        assert ERROR_INVALID_DELIVERY in content["error"]["error"]

    def test_export_document_object_not_found(self):
        """Test exporting document for non-existent object"""
        # Arrange
        url = reverse("hrm:job-description-export-detail-document", kwargs={"pk": 99999})

        # Act
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("libs.export_xlsx.storage.get_storage_backend")
    @patch("libs.export_document.mixins.convert_html_to_pdf")
    def test_export_document_s3_delivery(self, mock_convert, mock_get_storage):
        """Test exporting document with S3 link delivery"""
        # Arrange
        # Create a real temporary file
        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_file.write(b"fake pdf content")
        tmp_file.close()

        mock_convert.return_value = {
            "file_path": tmp_file.name,
            "file_name": f"job_description_{self.job_description.code}.pdf",
            "size": 16,
        }

        mock_storage = Mock()
        mock_storage.save.return_value = f"exports/job_description_{self.job_description.code}.pdf"
        mock_storage.get_url.return_value = "https://s3.amazonaws.com/bucket/file.pdf"
        mock_storage.get_file_size.return_value = 1024
        mock_get_storage.return_value = mock_storage

        url = reverse("hrm:job-description-export-detail-document", kwargs={"pk": self.job_description.pk})

        try:
            # Act
            response = self.client.get(url, {"delivery": "link"})

            # Assert
            assert response.status_code == status.HTTP_200_OK
            content = json.loads(response.content.decode())

            # Check if response is wrapped
            if "data" in content:
                data = content["data"]
            else:
                data = content

            assert "url" in data
            assert "filename" in data
            assert "expires_in" in data
            assert "storage_backend" in data
            assert data["url"] == "https://s3.amazonaws.com/bucket/file.pdf"
            assert data["storage_backend"] == "s3"
        finally:
            # Clean up
            if os.path.exists(tmp_file.name):
                os.unlink(tmp_file.name)

    @patch("libs.export_document.mixins.convert_html_to_pdf")
    def test_export_document_conversion_failure(self, mock_convert):
        """Test handling of conversion failure"""
        # Arrange
        mock_convert.side_effect = Exception("Conversion failed")
        url = reverse("hrm:job-description-export-detail-document", kwargs={"pk": self.job_description.pk})

        # Act
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        content = json.loads(response.content.decode())
        assert "error" in content or ("data" in content and content["data"] is None)


@pytest.mark.unit
class TestExportDocumentMixinUnit:
    """Unit tests for ExportDocumentMixin methods"""

    def test_direct_file_response(self):
        """Test _direct_file_response method"""
        # Arrange
        from libs.export_document.mixins import ExportDocumentMixin

        # Create a temporary file
        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_file.write(b"test content")
        tmp_file.close()

        mixin = ExportDocumentMixin()
        file_info = {
            "file_path": tmp_file.name,
            "file_name": "test.pdf",
            "size": 12,
        }

        try:
            # Act
            response = mixin._direct_file_response(file_info)

            # Assert
            assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
            assert response["Content-Type"] == "application/pdf"
            assert 'attachment; filename="test.pdf"' in response["Content-Disposition"]
            assert response.content == b"test content"
        finally:
            # Clean up
            if os.path.exists(tmp_file.name):
                os.unlink(tmp_file.name)

    def test_cleanup_temp_file(self):
        """Test _cleanup_temp_file method"""
        # Arrange
        from libs.export_document.mixins import ExportDocumentMixin

        # Create a temporary file
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        tmp_file.write(b"test")
        tmp_file.close()

        mixin = ExportDocumentMixin()

        # Act
        mixin._cleanup_temp_file(tmp_file.name)

        # Assert
        assert not os.path.exists(tmp_file.name)

    def test_cleanup_temp_file_nonexistent(self):
        """Test _cleanup_temp_file with non-existent file"""
        # Arrange
        from libs.export_document.mixins import ExportDocumentMixin

        mixin = ExportDocumentMixin()

        # Act & Assert - should not raise exception
        mixin._cleanup_temp_file("/tmp/nonexistent_file.pdf")
