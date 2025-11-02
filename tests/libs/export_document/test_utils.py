"""
Tests for document export utilities (HTML to PDF/DOCX conversion).
"""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from libs.export_document.utils import convert_html_to_docx, convert_html_to_pdf


@pytest.mark.unit
class TestConvertHtmlToPdf:
    """Test HTML to PDF conversion functionality"""

    def test_convert_simple_html_to_pdf(self):
        """Test converting a simple HTML template to PDF"""
        # Arrange
        template_name = "documents/job_description.html"
        context = {
            "job_description": Mock(
                code="JD001",
                title="Senior Python Developer",
                position_title="Senior Backend Developer",
                responsibility="Develop backend services",
                requirement="5+ years Python",
                preferred_criteria="Django experience",
                benefit="Competitive salary",
                proposed_salary="2000-3000 USD",
                note="Remote work",
            ),
        }
        filename = "test_job_description"

        # Act
        result = convert_html_to_pdf(template_name, context, filename)

        try:
            # Assert
            assert "file_path" in result
            assert "file_name" in result
            assert "size" in result
            assert result["file_name"] == "test_job_description.pdf"
            assert isinstance(result["size"], int)
            assert result["size"] > 0

            # Check file exists
            file_path = Path(result["file_path"])
            assert file_path.exists()

            # Read and verify it's a PDF
            with open(file_path, "rb") as f:
                pdf_header = f.read(4)
                assert pdf_header == b"%PDF"

        finally:
            # Clean up
            if "file_path" in result and os.path.exists(result["file_path"]):
                os.unlink(result["file_path"])

    def test_convert_html_to_pdf_filename_slugify(self):
        """Test that filename is properly slugified"""
        # Arrange
        template_name = "documents/job_description.html"
        context = {
            "job_description": Mock(
                code="JD002",
                title="Test",
                position_title="Test",
                responsibility="Test",
                requirement="Test",
                preferred_criteria="",
                benefit="Test",
                proposed_salary="1000 USD",
                note="",
            )
        }
        filename = "Test File Name With Spaces"

        # Act
        result = convert_html_to_pdf(template_name, context, filename)

        try:
            # Assert - filename should be slugified
            assert result["file_name"] == "test-file-name-with-spaces.pdf"
        finally:
            if "file_path" in result and os.path.exists(result["file_path"]):
                os.unlink(result["file_path"])

    @patch("weasyprint.HTML")
    def test_convert_html_to_pdf_conversion_failure(self, mock_html):
        """Test PDF conversion failure handling"""
        # Arrange
        mock_html.side_effect = Exception("WeasyPrint error")
        template_name = "documents/job_description.html"
        context = {"job_description": Mock(code="JD003")}
        filename = "test"

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            convert_html_to_pdf(template_name, context, filename)

        assert "WeasyPrint error" in str(exc_info.value)


@pytest.mark.unit
class TestConvertHtmlToDocx:
    """Test HTML to DOCX conversion functionality"""

    @patch("pypandoc.convert_file")
    def test_convert_simple_html_to_docx(self, mock_convert):
        """Test converting a simple HTML template to DOCX"""
        # Arrange
        template_name = "documents/job_description.html"
        context = {
            "job_description": Mock(
                code="JD001",
                title="Senior Python Developer",
                position_title="Senior Backend Developer",
                responsibility="Develop backend services",
                requirement="5+ years Python",
                preferred_criteria="Django experience",
                benefit="Competitive salary",
                proposed_salary="2000-3000 USD",
                note="Remote work",
            ),
        }
        filename = "test_job_description"

        # Mock pypandoc to create an actual file
        def mock_convert_side_effect(source, format, outputfile=None, extra_args=None):
            # Create a fake DOCX file
            with open(outputfile, "wb") as f:
                f.write(b"fake docx content")

        mock_convert.side_effect = mock_convert_side_effect

        # Act
        result = convert_html_to_docx(template_name, context, filename)

        try:
            # Assert
            assert "file_path" in result
            assert "file_name" in result
            assert "size" in result
            assert result["file_name"] == "test_job_description.docx"
            assert isinstance(result["size"], int)
            assert result["size"] > 0

            # Check file exists
            file_path = Path(result["file_path"])
            assert file_path.exists()

            mock_convert.assert_called_once()
        finally:
            # Clean up
            if "file_path" in result and os.path.exists(result["file_path"]):
                os.unlink(result["file_path"])

    @patch("pypandoc.convert_file")
    def test_convert_html_to_docx_filename_slugify(self, mock_convert):
        """Test that filename is properly slugified"""
        # Arrange
        template_name = "documents/job_description.html"
        context = {
            "job_description": Mock(
                code="JD002",
                title="Test",
                position_title="Test",
                responsibility="Test",
                requirement="Test",
                preferred_criteria="",
                benefit="Test",
                proposed_salary="1000 USD",
                note="",
            )
        }
        filename = "Test File Name With Spaces"

        def mock_convert_side_effect(source, format, outputfile=None, extra_args=None):
            with open(outputfile, "wb") as f:
                f.write(b"fake docx content")

        mock_convert.side_effect = mock_convert_side_effect

        # Act
        result = convert_html_to_docx(template_name, context, filename)

        try:
            # Assert - filename should be slugified
            assert result["file_name"] == "test-file-name-with-spaces.docx"
        finally:
            if "file_path" in result and os.path.exists(result["file_path"]):
                os.unlink(result["file_path"])

    @patch("pypandoc.convert_file")
    def test_convert_html_to_docx_conversion_failure(self, mock_convert):
        """Test DOCX conversion failure handling"""
        # Arrange
        mock_convert.side_effect = Exception("Pandoc error")
        template_name = "documents/job_description.html"
        context = {"job_description": Mock(code="JD003")}
        filename = "test"

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            convert_html_to_docx(template_name, context, filename)

        assert "Pandoc error" in str(exc_info.value)

    @patch("pypandoc.convert_file")
    def test_convert_html_to_docx_calls_pypandoc_correctly(self, mock_convert):
        """Test that pypandoc is called with correct parameters"""
        # Arrange
        template_name = "documents/job_description.html"
        context = {
            "job_description": Mock(
                code="JD001",
                title="Test",
                position_title="Test",
                responsibility="Test",
                requirement="Test",
                preferred_criteria="",
                benefit="Test",
                proposed_salary="1000",
                note="",
            ),
        }
        filename = "test"

        def mock_convert_side_effect(source, format, outputfile=None, extra_args=None):
            with open(outputfile, "wb") as f:
                f.write(b"fake docx content")

        mock_convert.side_effect = mock_convert_side_effect

        # Act
        result = convert_html_to_docx(template_name, context, filename)

        try:
            # Assert
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            assert call_args[0][1] == "docx"  # format argument
            assert call_args[1]["extra_args"] == ["--standalone"]
        finally:
            if "file_path" in result and os.path.exists(result["file_path"]):
                os.unlink(result["file_path"])
