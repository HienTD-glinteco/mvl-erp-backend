"""Tests for import serializer options validation."""

import pytest
from rest_framework.exceptions import ValidationError

from apps.imports.api.serializers import ImportStartSerializer
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
class TestImportStartSerializerOptionsValidation:
    """Test cases for ImportStartSerializer options validation."""

    def test_validate_options_empty_dict(self):
        """Test that empty options dict gets default values."""
        serializer = ImportStartSerializer()
        validated = serializer.validate_options({})

        assert validated["batch_size"] == DEFAULT_BATCH_SIZE
        assert validated["count_total_first"] == DEFAULT_COUNT_TOTAL_FIRST
        assert validated["header_rows"] == DEFAULT_HEADER_ROWS
        assert validated["output_format"] == DEFAULT_OUTPUT_FORMAT
        assert validated["create_result_file_records"] == DEFAULT_CREATE_RESULT_FILE_RECORDS
        assert validated["handler_options"] == {}

    def test_validate_options_unknown_key(self):
        """Test that unknown option keys are rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"unknown_key": "value"})

        assert "Invalid option key" in str(exc_info.value)

    def test_validate_options_batch_size_valid(self):
        """Test valid batch_size values."""
        serializer = ImportStartSerializer()

        # Test minimum
        validated = serializer.validate_options({"batch_size": MIN_BATCH_SIZE})
        assert validated["batch_size"] == MIN_BATCH_SIZE

        # Test maximum
        validated = serializer.validate_options({"batch_size": MAX_BATCH_SIZE})
        assert validated["batch_size"] == MAX_BATCH_SIZE

        # Test middle value
        validated = serializer.validate_options({"batch_size": 1000})
        assert validated["batch_size"] == 1000

    def test_validate_options_batch_size_invalid_type(self):
        """Test that non-integer batch_size is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"batch_size": "500"})

        assert "batch_size must be an integer" in str(exc_info.value)

    def test_validate_options_batch_size_out_of_range(self):
        """Test that batch_size outside valid range is rejected."""
        serializer = ImportStartSerializer()

        # Too small
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"batch_size": MIN_BATCH_SIZE - 1})
        assert "batch_size must be between" in str(exc_info.value)

        # Too large
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"batch_size": MAX_BATCH_SIZE + 1})
        assert "batch_size must be between" in str(exc_info.value)

    def test_validate_options_count_total_first_valid(self):
        """Test valid count_total_first values."""
        serializer = ImportStartSerializer()

        validated = serializer.validate_options({"count_total_first": True})
        assert validated["count_total_first"] is True

        validated = serializer.validate_options({"count_total_first": False})
        assert validated["count_total_first"] is False

    def test_validate_options_count_total_first_invalid_type(self):
        """Test that non-boolean count_total_first is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"count_total_first": "true"})

        assert "count_total_first must be a boolean" in str(exc_info.value)

    def test_validate_options_header_rows_valid(self):
        """Test valid header_rows values."""
        serializer = ImportStartSerializer()

        # Test minimum
        validated = serializer.validate_options({"header_rows": MIN_HEADER_ROWS})
        assert validated["header_rows"] == MIN_HEADER_ROWS

        # Test maximum
        validated = serializer.validate_options({"header_rows": MAX_HEADER_ROWS})
        assert validated["header_rows"] == MAX_HEADER_ROWS

        # Test middle value
        validated = serializer.validate_options({"header_rows": 5})
        assert validated["header_rows"] == 5

    def test_validate_options_header_rows_invalid_type(self):
        """Test that non-integer header_rows is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"header_rows": "1"})

        assert "header_rows must be an integer" in str(exc_info.value)

    def test_validate_options_header_rows_out_of_range(self):
        """Test that header_rows outside valid range is rejected."""
        serializer = ImportStartSerializer()

        # Too small
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"header_rows": MIN_HEADER_ROWS - 1})
        assert "header_rows must be between" in str(exc_info.value)

        # Too large
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"header_rows": MAX_HEADER_ROWS + 1})
        assert "header_rows must be between" in str(exc_info.value)

    def test_validate_options_output_format_valid(self):
        """Test valid output_format values."""
        serializer = ImportStartSerializer()

        validated = serializer.validate_options({"output_format": "csv"})
        assert validated["output_format"] == "csv"

        validated = serializer.validate_options({"output_format": "xlsx"})
        assert validated["output_format"] == "xlsx"

        # Test case-insensitive
        validated = serializer.validate_options({"output_format": "CSV"})
        assert validated["output_format"] == "csv"

        validated = serializer.validate_options({"output_format": "XLSX"})
        assert validated["output_format"] == "xlsx"

    def test_validate_options_output_format_invalid_type(self):
        """Test that non-string output_format is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"output_format": 123})

        assert "output_format must be a string" in str(exc_info.value)

    def test_validate_options_output_format_invalid_value(self):
        """Test that invalid output_format value is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"output_format": "json"})

        assert "output_format must be one of" in str(exc_info.value)

    def test_validate_options_create_result_file_records_valid(self):
        """Test valid create_result_file_records values."""
        serializer = ImportStartSerializer()

        validated = serializer.validate_options({"create_result_file_records": True})
        assert validated["create_result_file_records"] is True

        validated = serializer.validate_options({"create_result_file_records": False})
        assert validated["create_result_file_records"] is False

    def test_validate_options_create_result_file_records_invalid_type(self):
        """Test that non-boolean create_result_file_records is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"create_result_file_records": "true"})

        assert "create_result_file_records must be a boolean" in str(exc_info.value)

    def test_validate_options_handler_path_valid(self):
        """Test valid handler_path values."""
        serializer = ImportStartSerializer()

        # Valid string path
        validated = serializer.validate_options({"handler_path": "apps.hrm.handlers.employee_handler"})
        assert validated["handler_path"] == "apps.hrm.handlers.employee_handler"

        # Null is allowed
        validated = serializer.validate_options({"handler_path": None})
        assert validated["handler_path"] is None

    def test_validate_options_handler_path_invalid_type(self):
        """Test that non-string handler_path is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"handler_path": 123})

        assert "handler_path must be a string or null" in str(exc_info.value)

    def test_validate_options_handler_path_empty_string(self):
        """Test that empty string handler_path is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"handler_path": ""})

        assert "handler_path cannot be an empty string" in str(exc_info.value)

    def test_validate_options_handler_options_valid(self):
        """Test valid handler_options values."""
        serializer = ImportStartSerializer()

        # Empty dict
        validated = serializer.validate_options({"handler_options": {}})
        assert validated["handler_options"] == {}

        # Dict with custom keys
        custom_options = {"custom_key": "value", "another_key": 123}
        validated = serializer.validate_options({"handler_options": custom_options})
        assert validated["handler_options"] == custom_options

    def test_validate_options_handler_options_invalid_type(self):
        """Test that non-dict handler_options is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"handler_options": "not a dict"})

        assert "handler_options must be a dictionary" in str(exc_info.value)

    def test_validate_options_result_file_prefix_valid(self):
        """Test valid result_file_prefix values."""
        serializer = ImportStartSerializer()

        validated = serializer.validate_options({"result_file_prefix": "custom/prefix/"})
        assert validated["result_file_prefix"] == "custom/prefix/"

    def test_validate_options_result_file_prefix_invalid_type(self):
        """Test that non-string result_file_prefix is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options({"result_file_prefix": 123})

        assert "result_file_prefix must be a string" in str(exc_info.value)

    def test_validate_options_multiple_keys(self):
        """Test validation with multiple option keys."""
        serializer = ImportStartSerializer()

        options = {
            "batch_size": 1000,
            "count_total_first": False,
            "header_rows": 2,
            "output_format": "xlsx",
            "create_result_file_records": True,
            "handler_path": "apps.test.handler",
            "handler_options": {"key": "value"},
            "result_file_prefix": "test/",
        }

        validated = serializer.validate_options(options)

        assert validated["batch_size"] == 1000
        assert validated["count_total_first"] is False
        assert validated["header_rows"] == 2
        assert validated["output_format"] == "xlsx"
        assert validated["create_result_file_records"] is True
        assert validated["handler_path"] == "apps.test.handler"
        assert validated["handler_options"] == {"key": "value"}
        assert validated["result_file_prefix"] == "test/"

    def test_validate_options_not_dict(self):
        """Test that non-dict options value is rejected."""
        serializer = ImportStartSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_options("not a dict")

        assert "Options must be a dictionary" in str(exc_info.value)
