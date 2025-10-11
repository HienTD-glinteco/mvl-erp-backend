"""Tests for AutoCodeMixin."""

import unittest
from unittest.mock import MagicMock, patch

from libs.base_model_mixin import AutoCodeMixin


class MockModelWithAutoCode(AutoCodeMixin):
    """Mock model for testing AutoCodeMixin."""

    CODE_PREFIX = "TST"
    TEMP_CODE_PREFIX = "TEMP_"

    def __init__(self, *args, **kwargs):
        """Initialize mock model."""
        self.code = kwargs.get("code", "")
        self._state = MagicMock()
        self._state.adding = kwargs.get("is_new", True)

    def save(self, *args, **kwargs):
        """Override save to call parent implementation."""
        # Simulate parent save by calling AutoCodeMixin's save
        super().save(*args, **kwargs)


class AutoCodeMixinTest(unittest.TestCase):
    """Test cases for AutoCodeMixin."""

    @patch("libs.base_model_mixin.get_random_string")
    def test_generates_temp_code_for_new_instance_without_code(self, mock_random):
        """Test that mixin generates temp code for new instances without code."""
        # Arrange
        mock_random.return_value = "abc123xyz"
        instance = MockModelWithAutoCode(is_new=True, code="")

        # Act
        instance.save()

        # Assert
        self.assertEqual(instance.code, "TEMP_abc123xyz")
        mock_random.assert_called_once_with(20)

    def test_does_not_generate_temp_code_for_existing_instance(self):
        """Test that mixin does not generate temp code for existing instances."""
        # Arrange
        instance = MockModelWithAutoCode(is_new=False, code="PERM001")
        original_code = instance.code

        # Act
        instance.save()

        # Assert
        self.assertEqual(instance.code, original_code)

    def test_does_not_overwrite_existing_code(self):
        """Test that mixin does not overwrite existing code on new instances."""
        # Arrange
        instance = MockModelWithAutoCode(is_new=True, code="MANUAL001")
        original_code = instance.code

        # Act
        instance.save()

        # Assert
        self.assertEqual(instance.code, original_code)

    @patch("libs.base_model_mixin.get_random_string")
    def test_uses_custom_temp_prefix(self, mock_random):
        """Test that mixin uses custom TEMP_CODE_PREFIX if provided."""
        # Arrange
        mock_random.return_value = "xyz789"

        class CustomPrefixModel(AutoCodeMixin):
            CODE_PREFIX = "CUS"
            TEMP_CODE_PREFIX = "DRAFT_"

            def __init__(self):
                self.code = ""
                self._state = MagicMock()
                self._state.adding = True

        instance = CustomPrefixModel()

        # Act
        instance.save()

        # Assert
        self.assertEqual(instance.code, "DRAFT_xyz789")

    @patch("libs.base_model_mixin.get_random_string")
    def test_uses_default_temp_prefix_when_not_specified(self, mock_random):
        """Test that mixin uses default TEMP_ prefix when not specified."""
        # Arrange
        mock_random.return_value = "def456"

        class DefaultPrefixModel(AutoCodeMixin):
            CODE_PREFIX = "DEF"
            # TEMP_CODE_PREFIX not specified, should use default

            def __init__(self):
                self.code = ""
                self._state = MagicMock()
                self._state.adding = True

        instance = DefaultPrefixModel()

        # Act
        instance.save()

        # Assert
        self.assertEqual(instance.code, "TEMP_def456")

    def test_handles_model_without_code_attribute_gracefully(self):
        """Test that mixin handles models without code attribute gracefully."""
        # Arrange
        class ModelWithoutCode(AutoCodeMixin):
            CODE_PREFIX = "NOC"

            def __init__(self):
                # No code attribute
                self._state = MagicMock()
                self._state.adding = True

        instance = ModelWithoutCode()

        # Act & Assert - Should not raise an error
        try:
            instance.save()
        except AttributeError:
            self.fail("AutoCodeMixin raised AttributeError for model without code attribute")


class AutoCodeMixinIntegrationTest(unittest.TestCase):
    """Integration tests for AutoCodeMixin with custom save methods."""

    @patch("libs.base_model_mixin.get_random_string")
    def test_works_with_custom_save_logic(self, mock_random):
        """Test that mixin works when model has custom save logic."""
        # Arrange
        mock_random.return_value = "custom123"

        class ModelWithCustomSave(AutoCodeMixin):
            CODE_PREFIX = "CUS"
            TEMP_CODE_PREFIX = "TEMP_"

            def __init__(self):
                self.code = ""
                self.custom_field = None
                self._state = MagicMock()
                self._state.adding = True
                self.save_called = False

            def save(self, *args, **kwargs):
                # Custom logic before calling super
                self.custom_field = "custom_value"
                # Call super to get temp code generation
                super().save(*args, **kwargs)
                # Custom logic after
                self.save_called = True

        instance = ModelWithCustomSave()

        # Act
        instance.save()

        # Assert
        self.assertEqual(instance.code, "TEMP_custom123")
        self.assertEqual(instance.custom_field, "custom_value")
        self.assertTrue(instance.save_called)
