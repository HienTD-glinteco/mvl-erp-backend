"""
Tests for ExportDocumentMixin functionality.
"""

import os
import tempfile

import pytest
from rest_framework import status

from libs.export_document.mixins import ExportDocumentMixin


@pytest.mark.unit
class TestExportDocumentMixinUnit:
    """Unit tests for ExportDocumentMixin methods"""

    def test_direct_file_response(self):
        """Test _direct_file_response method"""
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
        mixin = ExportDocumentMixin()

        # Act & Assert - should not raise exception
        mixin._cleanup_temp_file("/tmp/nonexistent_file.pdf")
