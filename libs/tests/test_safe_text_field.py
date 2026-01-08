"""Tests for SafeTextField custom field."""

import pytest
from django.core.exceptions import ValidationError
from django.db import models

from libs.models import SafeTextField


class MockModel(models.Model):
    """Mock model for testing SafeTextField."""

    class Meta:
        app_label = "libs"


@pytest.mark.django_db
class TestSafeTextField:
    """Test cases for SafeTextField."""

    def test_clean_sanitizes_script_tags(self):
        """Test that script tags are removed during cleaning."""
        field = SafeTextField()
        value = '<p>Hello</p><script>alert("xss")</script>'
        model_instance = MockModel()

        result = field.clean(value, model_instance)

        assert "<script>" not in result
        assert "alert" not in result
        assert "<p>Hello</p>" in result

    def test_clean_sanitizes_onclick_attribute(self):
        """Test that onclick attributes are removed during cleaning."""
        field = SafeTextField()
        value = "<p onclick=\"alert('xss')\">Hello</p>"
        model_instance = MockModel()

        result = field.clean(value, model_instance)

        assert "onclick" not in result
        assert "Hello" in result

    def test_clean_preserves_safe_html(self):
        """Test that safe HTML content is preserved."""
        field = SafeTextField()
        value = "<p>Hello <strong>World</strong></p>"
        model_instance = MockModel()

        result = field.clean(value, model_instance)

        assert result == "<p>Hello <strong>World</strong></p>"

    def test_clean_validates_text_length_against_max_length(self):
        """Test that text content length is validated against max_length."""
        field = SafeTextField(max_length=10)
        value = "<p>This is a very long text that exceeds the limit</p>"
        model_instance = MockModel()

        with pytest.raises(ValidationError) as exc_info:
            field.clean(value, model_instance)

        assert "at most 10 characters" in str(exc_info.value)

    def test_clean_allows_text_within_max_length(self):
        """Test that text within max_length is allowed."""
        field = SafeTextField(max_length=50)
        value = "<p>Short text</p>"
        model_instance = MockModel()

        result = field.clean(value, model_instance)

        assert result == "<p>Short text</p>"

    def test_clean_counts_only_text_content_not_html_tags(self):
        """Test that max_length validation counts only text content, not HTML markup."""
        field = SafeTextField(max_length=15)
        # HTML has more than 15 chars but text "Hello World" is only 11 chars
        value = "<p><strong>Hello World</strong></p>"
        model_instance = MockModel()

        # Should not raise because text is only 11 characters
        result = field.clean(value, model_instance)

        assert result == "<p><strong>Hello World</strong></p>"

    def test_clean_with_html_that_exceeds_text_limit(self):
        """Test that HTML with text content exceeding max_length raises ValidationError."""
        field = SafeTextField(max_length=5)
        # Text content "Hello World" is 11 chars, exceeds limit of 5
        value = "<p>Hello World</p>"
        model_instance = MockModel()

        with pytest.raises(ValidationError) as exc_info:
            field.clean(value, model_instance)

        assert "at most 5 characters" in str(exc_info.value)
        assert "it has 11" in str(exc_info.value)

    def test_clean_without_max_length_skips_validation(self):
        """Test that when max_length is None, length validation is skipped."""
        field = SafeTextField()  # No max_length set
        value = "<p>" + "a" * 10000 + "</p>"
        model_instance = MockModel()

        # Should not raise
        result = field.clean(value, model_instance)

        assert "a" * 10000 in result

    def test_clean_handles_empty_value(self):
        """Test that empty value is handled correctly."""
        field = SafeTextField(max_length=50, blank=True)
        value = ""
        model_instance = MockModel()

        result = field.clean(value, model_instance)

        assert result == ""

    def test_clean_handles_whitespace_only_value(self):
        """Test that whitespace-only value is counted correctly."""
        field = SafeTextField(max_length=5)
        value = "<p>   </p>"  # 3 spaces
        model_instance = MockModel()

        result = field.clean(value, model_instance)

        assert "<p>" in result

    def test_clean_with_nested_html_tags(self):
        """Test max_length validation with deeply nested HTML."""
        field = SafeTextField(max_length=10)
        # Nested tags but text is only "Hello" -> 5 characters
        value = "<div><p><strong><em>Hello</em></strong></p></div>"
        model_instance = MockModel()

        result = field.clean(value, model_instance)

        assert "Hello" in result

    def test_clean_strips_dangerous_tags_before_length_check(self):
        """Test that dangerous tags are stripped before length validation."""
        field = SafeTextField(max_length=20)
        # After stripping script, text is only "Hello"
        value = "<p>Hello</p><script>dangerous code here</script>"
        model_instance = MockModel()

        result = field.clean(value, model_instance)

        assert "Hello" in result
        assert "dangerous" not in result

    def test_no_max_length_validator_in_default_validators(self):
        """Test that SafeTextField does NOT use MaxLengthValidator.

        Unlike CharField, TextField (which SafeTextField extends) does not add
        MaxLengthValidator to its validators. This ensures our custom BeautifulSoup-based
        length validation (which counts only text, not HTML) is the only length check.
        """
        from django.core.validators import MaxLengthValidator

        field = SafeTextField(max_length=100)

        # Verify no MaxLengthValidator is in the validators list
        validator_types = [type(v) for v in field.validators]
        assert MaxLengthValidator not in validator_types
