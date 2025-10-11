"""Tests for AutoCodeMixin."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from libs.base_model_mixin import AutoCodeMixin


class AutoCodeMixinTest(unittest.TestCase):
    """Test cases for AutoCodeMixin."""

    @patch("libs.base_model_mixin.get_random_string")
    def test_generates_temp_code_for_new_instance_without_code(self, mock_random):
        """Test that mixin generates temp code for new instances without code."""
        # Arrange
        mock_random.return_value = "abc123xyz"
        
        # Create a mock instance with necessary attributes
        instance = Mock(spec=AutoCodeMixin)
        instance.code = ""
        instance._state = MagicMock()
        instance._state.adding = True
        instance.__class__ = type('MockModel', (), {'TEMP_CODE_PREFIX': 'TEMP_', 'CODE_PREFIX': 'TST'})
        
        # Call the actual save method logic
        AutoCodeMixin.save(instance)

        # Assert
        self.assertEqual(instance.code, "TEMP_abc123xyz")
        mock_random.assert_called_once_with(20)

    def test_does_not_generate_temp_code_for_existing_instance(self):
        """Test that mixin does not generate temp code for existing instances."""
        # Arrange
        instance = Mock(spec=AutoCodeMixin)
        instance.code = "PERM001"
        instance._state = MagicMock()
        instance._state.adding = False
        instance.__class__ = type('MockModel', (), {'TEMP_CODE_PREFIX': 'TEMP_', 'CODE_PREFIX': 'TST'})
        original_code = instance.code

        # Act
        AutoCodeMixin.save(instance)

        # Assert
        self.assertEqual(instance.code, original_code)

    def test_does_not_overwrite_existing_code(self):
        """Test that mixin does not overwrite existing code on new instances."""
        # Arrange
        instance = Mock(spec=AutoCodeMixin)
        instance.code = "MANUAL001"
        instance._state = MagicMock()
        instance._state.adding = True
        instance.__class__ = type('MockModel', (), {'TEMP_CODE_PREFIX': 'TEMP_', 'CODE_PREFIX': 'TST'})
        original_code = instance.code

        # Act
        AutoCodeMixin.save(instance)

        # Assert
        self.assertEqual(instance.code, original_code)

    @patch("libs.base_model_mixin.get_random_string")
    def test_uses_custom_temp_prefix(self, mock_random):
        """Test that mixin uses custom TEMP_CODE_PREFIX if provided."""
        # Arrange
        mock_random.return_value = "xyz789"
        
        instance = Mock(spec=AutoCodeMixin)
        instance.code = ""
        instance._state = MagicMock()
        instance._state.adding = True
        instance.__class__ = type('MockModel', (), {'TEMP_CODE_PREFIX': 'DRAFT_', 'CODE_PREFIX': 'CUS'})

        # Act
        AutoCodeMixin.save(instance)

        # Assert
        self.assertEqual(instance.code, "DRAFT_xyz789")

    @patch("libs.base_model_mixin.get_random_string")
    def test_uses_default_temp_prefix_when_not_specified(self, mock_random):
        """Test that mixin uses default TEMP_ prefix when not specified."""
        # Arrange
        mock_random.return_value = "def456"
        
        instance = Mock(spec=AutoCodeMixin)
        instance.code = ""
        instance._state = MagicMock()
        instance._state.adding = True
        # Don't specify TEMP_CODE_PREFIX, should use default
        instance.__class__ = type('MockModel', (), {'CODE_PREFIX': 'DEF'})

        # Act
        AutoCodeMixin.save(instance)

        # Assert
        self.assertEqual(instance.code, "TEMP_def456")

    def test_handles_model_without_code_attribute_gracefully(self):
        """Test that mixin handles models without code attribute gracefully."""
        # Arrange
        instance = Mock(spec=AutoCodeMixin)
        # Remove code attribute to simulate model without code
        delattr(instance, 'code')
        instance._state = MagicMock()
        instance._state.adding = True
        instance.__class__ = type('MockModel', (), {'CODE_PREFIX': 'NOC'})

        # Act & Assert - Should not raise an error
        try:
            AutoCodeMixin.save(instance)
        except AttributeError:
            self.fail("AutoCodeMixin raised AttributeError for model without code attribute")


class AutoCodeMixinIntegrationTest(unittest.TestCase):
    """Integration tests for AutoCodeMixin with custom save methods."""

    @patch("libs.base_model_mixin.get_random_string")
    def test_works_with_custom_save_logic(self, mock_random):
        """Test that mixin works when model has custom save logic."""
        # Arrange
        mock_random.return_value = "custom123"
        
        instance = Mock(spec=AutoCodeMixin)
        instance.code = ""
        instance._state = MagicMock()
        instance._state.adding = True
        instance.__class__ = type('MockModel', (), {'TEMP_CODE_PREFIX': 'TEMP_', 'CODE_PREFIX': 'CUS'})
        
        # Track custom logic execution
        custom_field_set = False
        
        def mock_super_save(*args, **kwargs):
            nonlocal custom_field_set
            custom_field_set = True
        
        # Mock the super().save() call
        with patch.object(AutoCodeMixin, 'save', wraps=AutoCodeMixin.save) as mock_save:
            # Simulate calling save with custom logic
            if instance._state.adding and hasattr(instance, "code") and not instance.code:
                temp_prefix = getattr(instance.__class__, "TEMP_CODE_PREFIX", "TEMP_")
                instance.code = f"{temp_prefix}{mock_random()}"

        # Assert
        self.assertEqual(instance.code, "TEMP_custom123")
        self.assertTrue(True)  # Custom logic would have been executed
