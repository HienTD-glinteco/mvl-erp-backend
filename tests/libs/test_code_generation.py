"""Tests for code generation utilities."""

import unittest

from libs.code_generation import generate_model_code


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
        self.assertEqual(code, "TST001")

    def test_generate_code_two_digits(self):
        """Test code generation for two digit ID (id=12 -> TST012)."""
        # Arrange
        instance = MockModel(12)

        # Act
        code = generate_model_code(instance)

        # Assert
        self.assertEqual(code, "TST012")

    def test_generate_code_three_digits(self):
        """Test code generation for three digit ID (id=444 -> TST444)."""
        # Arrange
        instance = MockModel(444)

        # Act
        code = generate_model_code(instance)

        # Assert
        self.assertEqual(code, "TST444")

    def test_generate_code_four_digits(self):
        """Test code generation for four digit ID (id=5555 -> TST5555)."""
        # Arrange
        instance = MockModel(5555)

        # Act
        code = generate_model_code(instance)

        # Assert
        self.assertEqual(code, "TST5555")

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
