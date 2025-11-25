"""Tests for mail template services."""

import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from apps.mailtemplates.services import (
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateValidationError,
    get_template_metadata,
    html_to_text,
    load_template_content,
    render_and_prepare_email,
    render_template_content,
    sanitize_html_for_storage,
    save_template_content,
    validate_template_data,
)


class TemplateServicesTestCase(TestCase):
    """Test cases for template service functions."""

    def test_get_template_metadata_success(self):
        """Test getting template metadata by slug."""
        # Arrange & Act
        metadata = get_template_metadata("welcome")

        # Assert
        self.assertEqual(metadata["slug"], "welcome")
        self.assertEqual(metadata["filename"], "welcome.html")
        self.assertIn("employee_fullname", [v["name"] for v in metadata["variables"]])

    def test_get_template_metadata_not_found(self):
        """Test getting non-existent template raises error."""
        # Arrange & Act & Assert
        with self.assertRaises(TemplateNotFoundError):
            get_template_metadata("non_existent")

    def test_sanitize_html_for_storage(self):
        """Test HTML sanitization removes dangerous content."""
        # Arrange
        dangerous_html = '<script>alert("xss")</script><p onclick="alert()">Hello</p>'

        # Act
        sanitized = sanitize_html_for_storage(dangerous_html)

        # Assert
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("onclick", sanitized)
        self.assertIn("Hello", sanitized)

    def test_sanitize_html_preserves_safe_content(self):
        """Test HTML sanitization preserves safe tags."""
        # Arrange
        safe_html = '<p>Hello <strong>World</strong></p><a href="http://example.com">Link</a>'

        # Act
        sanitized = sanitize_html_for_storage(safe_html)

        # Assert
        self.assertIn("<p>", sanitized)
        self.assertIn("<strong>", sanitized)
        self.assertIn("<a", sanitized)
        self.assertIn("href", sanitized)

    def test_render_template_content_success(self):
        """Test template rendering with valid data."""
        # Arrange
        template = "Hello {{ name }}!"
        data = {"name": "John"}

        # Act
        result = render_template_content(template, data)

        # Assert
        self.assertEqual(result, "Hello John!")

    def test_render_template_content_missing_variable_strict(self):
        """Test template rendering fails with missing variable in strict mode."""
        # Arrange
        template = "Hello {{ name }}!"
        data = {}

        # Act & Assert
        with self.assertRaises(TemplateRenderError):
            render_template_content(template, data, strict=True)

    def test_html_to_text(self):
        """Test HTML to plain text conversion."""
        # Arrange
        html = "<p>Hello <strong>World</strong></p><br><p>Test</p>"

        # Act
        text = html_to_text(html)

        # Assert
        self.assertIn("Hello World", text)
        self.assertIn("Test", text)
        self.assertNotIn("<p>", text)
        self.assertNotIn("<strong>", text)

    def test_validate_template_data_success(self):
        """Test data validation passes with valid data."""
        # Arrange
        template_meta = get_template_metadata("welcome")
        data = {
            "employee_fullname": "John Doe",
            "employee_email": "john.doe@example.com",
            "employee_username": "john.doe",
            "employee_start_date": "2025-11-01",
            "employee_code": "MVL001",
            "employee_department_name": "Sales",
            "new_password": "Abc12345",
            "logo_image_url": "/static/img/email_logo.png",
        }

        # Act & Assert (should not raise)
        validate_template_data(data, template_meta)

    def test_validate_template_data_missing_required(self):
        """Test data validation fails with missing required field."""
        # Arrange
        template_meta = get_template_metadata("welcome")
        data = {}  # Missing required fields

        # Act & Assert
        with self.assertRaises(TemplateValidationError):
            validate_template_data(data, template_meta)

    @override_settings(MAIL_TEMPLATE_DIR=tempfile.mkdtemp())
    def test_save_and_load_template_content(self):
        """Test saving and loading template content."""
        # Arrange
        filename = "test_template.html"
        content = "<html><body>Test {{ var }}</body></html>"

        # Act
        save_template_content(filename, content, create_backup=False)
        loaded_content = load_template_content(filename)

        # Assert
        self.assertEqual(loaded_content, content)

    @override_settings(MAIL_TEMPLATE_DIR=tempfile.mkdtemp())
    def test_save_template_creates_backup(self):
        """Test that saving creates a backup of existing file."""
        # Arrange
        filename = "test_backup.html"
        original_content = "<html>Original</html>"
        new_content = "<html>New</html>"

        # Act
        save_template_content(filename, original_content, create_backup=False)
        save_template_content(filename, new_content, create_backup=True)

        # Assert
        loaded_content = load_template_content(filename)
        self.assertEqual(loaded_content, new_content)

        # Check backup file exists
        from django.conf import settings

        template_dir = Path(settings.MAIL_TEMPLATE_DIR)
        backup_files = list(template_dir.glob("test_backup.bak.*"))
        self.assertGreater(len(backup_files), 0)


class RenderAndPrepareEmailTestCase(TestCase):
    """Test cases for complete email rendering pipeline."""

    def test_render_and_prepare_email_success(self):
        """Test complete rendering pipeline."""
        # Arrange
        template_meta = get_template_metadata("welcome")
        data = {
            "employee_fullname": "Jane Doe",
            "employee_email": "jane.doe@example.com",
            "employee_username": "jane.doe",
            "employee_start_date": "2025-12-01",
            "employee_code": "MVL001",
            "employee_department_name": "IT",
            "new_password": "Abc12345",
            "logo_image_url": "/static/img/email_logo.png",
        }

        # Act
        result = render_and_prepare_email(template_meta, data, validate=True)

        # Assert
        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertIn("Jane", result["html"])
        self.assertIn("Jane", result["text"])

    def test_render_and_prepare_email_validation_error(self):
        """Test rendering fails with invalid data."""
        # Arrange
        template_meta = get_template_metadata("welcome")
        data = {}  # Missing required fields

        # Act & Assert
        with self.assertRaises(TemplateValidationError):
            render_and_prepare_email(template_meta, data, validate=True)
