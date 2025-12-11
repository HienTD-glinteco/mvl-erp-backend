"""Tests for code generation utilities."""

import unittest
from unittest.mock import MagicMock, patch

from libs.code_generation import (
    create_auto_code_signal_handler,
    generate_model_code,
    register_auto_code_signal,
)


class MockModel:
    """Mock model class for testing."""

    CODE_PREFIX = "TST"

    def __init__(self, instance_id):
        self.id = instance_id


class GenerateModelCodeTest(unittest.TestCase):
    """Test cases for generate_model_code function."""

    def test_generate_code_single_digit(self):
        """Test code generation for single digit ID (id=1 -> TST001)."""
        # Arrange
        instance = MockModel(1)

        # Act
        code = generate_model_code(instance)

        # Assert
        self.assertEqual(code, "TST000000001")

    def test_generate_code_two_digits(self):
        """Test code generation for two digit ID (id=12 -> TST000000012)."""
        # Arrange
        instance = MockModel(12)

        # Act
        code = generate_model_code(instance)

        # Assert
        self.assertEqual(code, "TST000000012")

    def test_generate_code_three_digits(self):
        """Test code generation for three digit ID (id=444 -> TST000000444)."""
        # Arrange
        instance = MockModel(444)

        # Act
        code = generate_model_code(instance)

        # Assert
        self.assertEqual(code, "TST000000444")

    def test_generate_code_four_digits(self):
        """Test code generation for four digit ID (id=5555 -> TST000005555)."""
        # Arrange
        instance = MockModel(5555)

        # Act
        code = generate_model_code(instance)

        # Assert
        self.assertEqual(code, "TST000005555")

    def test_generate_code_without_prefix_raises_error(self):
        """Test that missing CODE_PREFIX raises AttributeError."""

        # Arrange
        class ModelWithoutPrefix:
            def __init__(self):
                self.id = 1

        instance = ModelWithoutPrefix()

        # Act & Assert
        with self.assertRaises(AttributeError) as context:
            generate_model_code(instance)

        self.assertIn("CODE_PREFIX", str(context.exception))

    def test_generate_code_without_id_raises_error(self):
        """Test that missing id raises ValueError."""

        # Arrange
        class ModelWithoutId:
            CODE_PREFIX = "TST"

            def __init__(self):
                self.id = None

        instance = ModelWithoutId()

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            generate_model_code(instance)

        self.assertIn("must have an id", str(context.exception))


class CreateAutoCodeSignalHandlerTest(unittest.TestCase):
    """Test cases for create_auto_code_signal_handler function."""

    def test_handler_generates_code_for_new_instance_with_temp_code(self):
        """Test that handler generates code for new instances with temporary code."""
        # Arrange
        handler = create_auto_code_signal_handler("TEMP_")
        mock_instance = MagicMock()
        mock_instance.code = "TEMP_abc123"
        mock_instance.id = 42
        mock_instance.__class__.CODE_PREFIX = "TST"

        # Act
        handler(sender=MagicMock, instance=mock_instance, created=True)

        # Assert
        # Verify generate_model_code was called and code was updated
        self.assertEqual(mock_instance.code, "TST000000042")
        mock_instance.save.assert_called_once_with(update_fields=["code"])

    def test_handler_ignores_existing_instances(self):
        """Test that handler does not generate code for existing instances."""
        # Arrange
        handler = create_auto_code_signal_handler("TEMP_")
        mock_instance = MagicMock()
        mock_instance.code = "TEMP_abc123"
        mock_instance.id = 42
        mock_instance.__class__.CODE_PREFIX = "TST"

        # Act
        handler(sender=MagicMock, instance=mock_instance, created=False)

        # Assert
        # Code should not be changed
        self.assertEqual(mock_instance.code, "TEMP_abc123")
        mock_instance.save.assert_not_called()

    def test_handler_ignores_instances_without_temp_code(self):
        """Test that handler does not generate code for instances without temporary code."""
        # Arrange
        handler = create_auto_code_signal_handler("TEMP_")
        mock_instance = MagicMock()
        mock_instance.code = "PERM001"
        mock_instance.id = 42
        mock_instance.__class__.CODE_PREFIX = "TST"

        # Act
        handler(sender=MagicMock, instance=mock_instance, created=True)

        # Assert
        # Code should not be changed
        self.assertEqual(mock_instance.code, "PERM001")
        mock_instance.save.assert_not_called()

    def test_handler_ignores_instances_without_code_attribute(self):
        """Test that handler gracefully handles instances without code attribute."""
        # Arrange
        handler = create_auto_code_signal_handler("TEMP_")
        mock_instance = MagicMock(spec=[])
        del mock_instance.code
        mock_instance.save = MagicMock()

        # Act
        handler(sender=MagicMock, instance=mock_instance, created=True)

        # Assert
        # Should not raise error, just do nothing
        mock_instance.save.assert_not_called()

    def test_handler_with_custom_temp_prefix(self):
        """Test handler with a custom temporary code prefix."""
        # Arrange
        handler = create_auto_code_signal_handler("CUSTOM_")
        mock_instance = MagicMock()
        mock_instance.code = "CUSTOM_xyz789"
        mock_instance.id = 99
        mock_instance.__class__.CODE_PREFIX = "TST"

        # Act
        handler(sender=MagicMock, instance=mock_instance, created=True)

        # Assert
        self.assertEqual(mock_instance.code, "TST000000099")
        mock_instance.save.assert_called_once_with(update_fields=["code"])

    def test_handler_with_custom_generate_code_function(self):
        """Test handler with custom code generation function."""

        # Arrange
        def custom_code_gen(instance):
            return f"{instance.__class__.CODE_PREFIX}{instance.id:05d}"

        handler = create_auto_code_signal_handler("TEMP_", custom_generate_code=custom_code_gen)
        mock_instance = MagicMock()
        mock_instance.code = "TEMP_abc123"
        mock_instance.id = 42
        mock_instance.__class__.CODE_PREFIX = "CUS"

        # Act
        handler(sender=MagicMock, instance=mock_instance, created=True)

        # Assert
        self.assertEqual(mock_instance.code, "CUS00042")
        mock_instance.save.assert_called_once_with(update_fields=["code"])

    def test_handler_uses_default_when_custom_generate_code_is_none(self):
        """Test that handler uses default generate_model_code when custom is None."""
        # Arrange
        handler = create_auto_code_signal_handler("TEMP_", custom_generate_code=None)
        mock_instance = MagicMock()
        mock_instance.code = "TEMP_xyz"
        mock_instance.id = 5
        mock_instance.__class__.CODE_PREFIX = "DEF"

        # Act
        handler(sender=MagicMock, instance=mock_instance, created=True)

        # Assert
        self.assertEqual(mock_instance.code, "DEF000000005")
        mock_instance.save.assert_called_once_with(update_fields=["code"])


class RegisterAutoCodeSignalTest(unittest.TestCase):
    """Test cases for register_auto_code_signal function."""

    @patch("libs.code_generation.post_save")
    def test_register_single_model(self, mock_post_save):
        """Test registering signal for a single model."""
        # Arrange
        mock_model = MagicMock()

        # Act
        register_auto_code_signal(mock_model)

        # Assert
        mock_post_save.connect.assert_called_once()
        call_args = mock_post_save.connect.call_args
        self.assertEqual(call_args[1]["sender"], mock_model)
        self.assertEqual(call_args[1]["weak"], False)

    @patch("libs.code_generation.post_save")
    def test_register_multiple_models(self, mock_post_save):
        """Test registering signal for multiple models."""
        # Arrange
        mock_model1 = MagicMock()
        mock_model2 = MagicMock()
        mock_model3 = MagicMock()

        # Act
        register_auto_code_signal(mock_model1, mock_model2, mock_model3)

        # Assert
        self.assertEqual(mock_post_save.connect.call_count, 3)
        # Verify each model was registered
        call_args_list = mock_post_save.connect.call_args_list
        registered_models = [call_args[1]["sender"] for call_args in call_args_list]
        self.assertIn(mock_model1, registered_models)
        self.assertIn(mock_model2, registered_models)
        self.assertIn(mock_model3, registered_models)

    @patch("libs.code_generation.post_save")
    def test_register_with_custom_temp_prefix(self, mock_post_save):
        """Test registering signal with a custom temporary code prefix."""
        # Arrange
        mock_model = MagicMock()

        # Act
        register_auto_code_signal(mock_model, temp_code_prefix="CUSTOM_")

        # Assert
        mock_post_save.connect.assert_called_once()
        # Handler should be created with custom prefix
        call_args = mock_post_save.connect.call_args
        handler = call_args[0][0]
        # Test the handler works with custom prefix
        mock_instance = MagicMock()
        mock_instance.code = "CUSTOM_test"
        mock_instance.id = 1
        mock_instance.__class__.CODE_PREFIX = "TST"
        handler(sender=mock_model, instance=mock_instance, created=True)
        self.assertEqual(mock_instance.code, "TST000000001")

    @patch("libs.code_generation.post_save")
    def test_register_with_custom_generate_code(self, mock_post_save):
        """Test registering signal with custom code generation function."""
        # Arrange
        mock_model = MagicMock()

        def custom_code_gen(instance):
            return f"{instance.__class__.CODE_PREFIX}-{instance.id:04d}"

        # Act
        register_auto_code_signal(mock_model, custom_generate_code=custom_code_gen)

        # Assert
        mock_post_save.connect.assert_called_once()
        # Handler should be created with custom code generation
        call_args = mock_post_save.connect.call_args
        handler = call_args[0][0]
        # Test the handler works with custom code generation
        mock_instance = MagicMock()
        mock_instance.code = "TEMP_test"
        mock_instance.id = 99
        mock_instance.__class__.CODE_PREFIX = "CUS"
        handler(sender=mock_model, instance=mock_instance, created=True)
        self.assertEqual(mock_instance.code, "CUS-0099")
