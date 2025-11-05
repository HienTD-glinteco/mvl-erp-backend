"""Tests for import serializer options validation."""

import pytest

from apps.imports.api.serializers import ImportOptionsSerializer
from apps.imports.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_COUNT_TOTAL_FIRST,
    DEFAULT_CREATE_RESULT_FILE_RECORDS,
    DEFAULT_HEADER_ROWS,
    DEFAULT_OUTPUT_FORMAT,
    MAX_BATCH_SIZE,
    MAX_HEADER_ROWS,
    MIN_BATCH_SIZE,
    MIN_HEADER_ROWS,
)


@pytest.mark.django_db
class TestImportOptionsSerializerValidation:
    """Test cases for ImportOptionsSerializer validation."""

    def test_validate_options_empty_dict(self):
        """Test that empty options dict gets default values."""
        serializer = ImportOptionsSerializer(data={})
        assert serializer.is_valid()
        validated = serializer.validated_data

        assert validated["batch_size"] == DEFAULT_BATCH_SIZE
        assert validated["count_total_first"] == DEFAULT_COUNT_TOTAL_FIRST
        assert validated["header_rows"] == DEFAULT_HEADER_ROWS
        assert validated["output_format"] == DEFAULT_OUTPUT_FORMAT
        assert validated["create_result_file_records"] == DEFAULT_CREATE_RESULT_FILE_RECORDS
        assert validated["handler_options"] == {}

    def test_validate_options_unknown_key(self):
        """Test that unknown option keys are rejected."""
        serializer = ImportOptionsSerializer(data={"unknown_key": "value"})
        assert not serializer.is_valid()
        assert "unknown_key" in serializer.errors

    def test_validate_options_batch_size_valid(self):
        """Test valid batch_size values."""
        # Test minimum
        serializer = ImportOptionsSerializer(data={"batch_size": MIN_BATCH_SIZE})
        assert serializer.is_valid()
        assert serializer.validated_data["batch_size"] == MIN_BATCH_SIZE

        # Test maximum
        serializer = ImportOptionsSerializer(data={"batch_size": MAX_BATCH_SIZE})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["batch_size"] == MAX_BATCH_SIZE

        # Test middle value
        serializer = ImportOptionsSerializer(data={"batch_size": 1000})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["batch_size"] == 1000

    def test_validate_options_batch_size_invalid_type(self):
        """Test that non-integer batch_size is rejected."""
        serializer = ImportOptionsSerializer(data={"batch_size": "500"})
        assert not serializer.is_valid()

    def test_validate_options_batch_size_out_of_range(self):
        """Test that batch_size outside valid range is rejected."""
        serializer = ImportOptionsSerializer(data={})

        # Too small
        serializer = ImportOptionsSerializer(data={"batch_size": MIN_BATCH_SIZE - 1})
        assert not serializer.is_valid()

        # Too large
        serializer = ImportOptionsSerializer(data={"batch_size": MAX_BATCH_SIZE + 1})
        assert not serializer.is_valid()

    def test_validate_options_count_total_first_valid(self):
        """Test valid count_total_first values."""
        serializer = ImportOptionsSerializer(data={"count_total_first": True})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["count_total_first"] is True

        serializer = ImportOptionsSerializer(data={"count_total_first": False})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["count_total_first"] is False

    def test_validate_options_count_total_first_invalid_type(self):
        """Test that non-boolean count_total_first is rejected."""
        serializer = ImportOptionsSerializer(data={"count_total_first": "true"})
        assert not serializer.is_valid()

    def test_validate_options_header_rows_valid(self):
        """Test valid header_rows values."""
        serializer = ImportOptionsSerializer(data={})

        # Test minimum
        serializer = ImportOptionsSerializer(data={"header_rows": MIN_HEADER_ROWS})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["header_rows"] == MIN_HEADER_ROWS

        # Test maximum
        serializer = ImportOptionsSerializer(data={"header_rows": MAX_HEADER_ROWS})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["header_rows"] == MAX_HEADER_ROWS

        # Test middle value
        serializer = ImportOptionsSerializer(data={"header_rows": 5})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["header_rows"] == 5

    def test_validate_options_header_rows_invalid_type(self):
        """Test that non-integer header_rows is rejected."""
        serializer = ImportOptionsSerializer(data={"header_rows": "1"})
        assert not serializer.is_valid()

    def test_validate_options_header_rows_out_of_range(self):
        """Test that header_rows outside valid range is rejected."""
        serializer = ImportOptionsSerializer(data={})

        # Too small
        serializer = ImportOptionsSerializer(data={"header_rows": MIN_HEADER_ROWS - 1})
        assert not serializer.is_valid()

        # Too large
        serializer = ImportOptionsSerializer(data={"header_rows": MAX_HEADER_ROWS + 1})
        assert not serializer.is_valid()

    def test_validate_options_output_format_valid(self):
        """Test valid output_format values."""
        serializer = ImportOptionsSerializer(data={"output_format": "csv"})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["output_format"] == "csv"

        serializer = ImportOptionsSerializer(data={"output_format": "xlsx"})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["output_format"] == "xlsx"

        # Test case-insensitive
        serializer = ImportOptionsSerializer(data={"output_format": "CSV"})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["output_format"] == "csv"

        serializer = ImportOptionsSerializer(data={"output_format": "XLSX"})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["output_format"] == "xlsx"

    def test_validate_options_output_format_invalid_type(self):
        """Test that non-string output_format is rejected."""
        serializer = ImportOptionsSerializer(data={"output_format": 123})
        assert not serializer.is_valid()

    def test_validate_options_output_format_invalid_value(self):
        """Test that invalid output_format value is rejected."""
        serializer = ImportOptionsSerializer(data={"output_format": "json"})
        assert not serializer.is_valid()

    def test_validate_options_create_result_file_records_valid(self):
        """Test valid create_result_file_records values."""
        serializer = ImportOptionsSerializer(data={"create_result_file_records": True})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["create_result_file_records"] is True

        serializer = ImportOptionsSerializer(data={"create_result_file_records": False})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["create_result_file_records"] is False

    def test_validate_options_create_result_file_records_invalid_type(self):
        """Test that non-boolean create_result_file_records is rejected."""
        serializer = ImportOptionsSerializer(data={"create_result_file_records": "true"})
        assert not serializer.is_valid()

    def test_validate_options_handler_path_valid(self):
        """Test valid handler_path values."""
        serializer = ImportOptionsSerializer(data={})

        # Valid string path
        serializer = ImportOptionsSerializer(data={"handler_path": "apps.hrm.handlers.employee_handler"})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["handler_path"] == "apps.hrm.handlers.employee_handler"

        # Null is allowed
        serializer = ImportOptionsSerializer(data={"handler_path": None})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["handler_path"] is None

    def test_validate_options_handler_path_invalid_type(self):
        """Test that non-string handler_path is rejected."""
        serializer = ImportOptionsSerializer(data={"handler_path": 123})
        assert not serializer.is_valid()

    def test_validate_options_handler_path_empty_string(self):
        """Test that empty string handler_path is rejected."""
        serializer = ImportOptionsSerializer(data={"handler_path": ""})
        assert not serializer.is_valid()

    def test_validate_options_handler_options_valid(self):
        """Test valid handler_options values."""
        # Empty dict
        serializer = ImportOptionsSerializer(data={"handler_options": {}})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["handler_options"] == {}

        # Dict with custom keys
        custom_options = {"custom_key": "value", "another_key": 123}
        serializer = ImportOptionsSerializer(data={"handler_options": custom_options})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["handler_options"] == custom_options

    def test_validate_options_handler_options_invalid_type(self):
        """Test that non-dict handler_options is rejected."""
        serializer = ImportOptionsSerializer(data={"handler_options": "not a dict"})
        assert not serializer.is_valid()

    def test_validate_options_result_file_prefix_valid(self):
        """Test valid result_file_prefix values."""
        serializer = ImportOptionsSerializer(data={"result_file_prefix": "custom/prefix/"})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["result_file_prefix"] == "custom/prefix/"

    def test_validate_options_result_file_prefix_invalid_type(self):
        """Test that non-string result_file_prefix is rejected."""
        serializer = ImportOptionsSerializer(data={"result_file_prefix": 123})
        assert not serializer.is_valid()

    def test_validate_options_allow_update_valid(self):
        """Test valid allow_update values."""
        # Test True
        serializer = ImportOptionsSerializer(data={"allow_update": True})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["allow_update"] is True

        # Test False
        serializer = ImportOptionsSerializer(data={"allow_update": False})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["allow_update"] is False

    def test_validate_options_allow_update_invalid_type(self):
        """Test that non-boolean allow_update is rejected."""
        serializer = ImportOptionsSerializer(data={"allow_update": "true"})
        assert not serializer.is_valid()

    def test_validate_options_allow_update_default(self):
        """Test that allow_update defaults to False."""
        serializer = ImportOptionsSerializer(data={})
        assert serializer.is_valid()
        validated = serializer.validated_data
        assert validated["allow_update"] is False

    def test_validate_options_multiple_keys(self):
        """Test validation with multiple option keys."""
        options = {
            "batch_size": 1000,
            "count_total_first": False,
            "header_rows": 2,
            "output_format": "xlsx",
            "create_result_file_records": True,
            "handler_path": "apps.test.handler",
            "handler_options": {"key": "value"},
            "result_file_prefix": "test/",
            "allow_update": True,
        }

        serializer = ImportOptionsSerializer(data=options)
        assert serializer.is_valid()
        validated = serializer.validated_data

        assert validated["batch_size"] == 1000
        assert validated["count_total_first"] is False
        assert validated["header_rows"] == 2
        assert validated["output_format"] == "xlsx"
        assert validated["create_result_file_records"] is True
        assert validated["handler_path"] == "apps.test.handler"
        assert validated["handler_options"] == {"key": "value"}
        assert validated["result_file_prefix"] == "test/"
        assert validated["allow_update"] is True

    def test_validate_options_not_dict(self):
        """Test that non-dict options value is rejected at the parent serializer level."""
        # This test is now handled at the ImportStartSerializer level
        # ImportOptionsSerializer expects dict data, passing a string directly doesn't make sense
        # Testing that unknown keys are rejected instead
        serializer = ImportOptionsSerializer(data={"invalid_key": "value"})
        assert not serializer.is_valid()
        assert "invalid_key" in serializer.errors
