"""Tests for import result file generation with proper encoding and error handling."""

import csv
import tempfile
from pathlib import Path

from apps.imports.tasks import sanitize_error_message
from apps.imports.utils import CSVStreamingWriter


class TestSanitizeErrorMessage:
    """Test cases for sanitize_error_message function."""

    def test_sanitize_empty_message(self):
        """Test sanitizing empty error message."""
        assert sanitize_error_message("") == ""
        assert sanitize_error_message(None) == ""

    def test_sanitize_simple_message(self):
        """Test sanitizing simple error message."""
        result = sanitize_error_message("User not found")
        assert result == "User not found"

    def test_sanitize_newlines(self):
        """Test removing newlines from error message."""
        error = 'duplicate key value violates unique constraint "hrm_employee_email"\nDETAIL: Key (email)=(test@example.com) already exists.'
        result = sanitize_error_message(error)
        assert "\n" not in result
        assert "\r" not in result
        assert "duplicate key value" in result
        assert "DETAIL:" in result

    def test_sanitize_multiline_postgres_error(self):
        """Test sanitizing multi-line PostgreSQL error."""
        error = 'duplicate key value violates unique constraint "hrm_employee_email_4937bc23_uniq"\nDETAIL:  ( (Key (email)=(daond@maivietland.vn) already exists.))'
        result = sanitize_error_message(error)
        assert "\n" not in result
        assert "duplicate key value" in result
        assert "daond@maivietland.vn" in result

    def test_sanitize_multiple_spaces(self):
        """Test removing multiple consecutive spaces."""
        error = "Error    with    multiple     spaces"
        result = sanitize_error_message(error)
        assert "  " not in result
        assert result == "Error with multiple spaces"

    def test_sanitize_null_bytes(self):
        """Test removing NULL bytes from error message."""
        error = "Error\x00with\x00null\x00bytes"
        result = sanitize_error_message(error)
        assert "\x00" not in result
        # NULL bytes are replaced, result doesn't have spaces since there were no spaces in original
        assert result == "Errorwithnullbytes"

    def test_sanitize_long_message(self):
        """Test truncating very long error messages."""
        long_error = "A" * 600  # 600 characters
        result = sanitize_error_message(long_error)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")

    def test_sanitize_carriage_returns(self):
        """Test removing carriage returns."""
        error = "Error\rwith\rcarriage\rreturns"
        result = sanitize_error_message(error)
        assert "\r" not in result
        assert result == "Error with carriage returns"


class TestCSVStreamingWriter:
    """Test cases for CSVStreamingWriter with UTF-8-sig encoding."""

    def test_csv_writer_uses_utf8_sig_encoding(self):
        """Test that CSV writer uses utf-8-sig encoding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = CSVStreamingWriter("test.csv", temp_dir=temp_dir)
            assert writer.temp_file.encoding == "utf-8-sig"
            writer.close()

    def test_csv_writer_handles_vietnamese_characters(self):
        """Test that CSV writer correctly handles Vietnamese characters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = "test_vietnamese.csv"
            writer = CSVStreamingWriter(filename, temp_dir=temp_dir)

            # Write headers with Vietnamese
            headers = ["Tên", "Email", "Địa chỉ"]
            writer.write_header(headers)

            # Write data with Vietnamese
            row = ["Nguyễn Văn A", "nguyenvana@example.com", "Hà Nội"]
            writer.write_row(row)
            writer.close()

            # Read back and verify
            file_path = Path(temp_dir) / filename
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                read_headers = next(reader)
                assert read_headers == headers

                read_row = next(reader)
                assert read_row == row

    def test_csv_writer_handles_special_characters(self):
        """Test that CSV writer properly escapes special characters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = "test_special.csv"
            writer = CSVStreamingWriter(filename, temp_dir=temp_dir)

            # Write headers
            headers = ["Name", "Error"]
            writer.write_header(headers)

            # Write row with quotes and commas
            row = ["Test User", 'Error: "duplicate key" value, constraint violated']
            writer.write_row(row)
            writer.close()

            # Read back and verify
            file_path = Path(temp_dir) / filename
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                read_row = next(reader)
                assert read_row == row

    def test_csv_writer_with_import_error_column(self):
        """Test CSV writer with Import Error column (like failed file)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = "test_failed.csv"
            writer = CSVStreamingWriter(filename, temp_dir=temp_dir)

            # Write headers with Import Error column
            headers = ["Column 1", "Column 2", "Import Error"]
            writer.write_header(headers)

            # Write row with sanitized error
            error_msg = 'duplicate key violates constraint "unique_email"\nDETAIL: Key already exists'
            sanitized_error = sanitize_error_message(error_msg)
            row = ["value1", "value2", sanitized_error]
            writer.write_row(row)
            writer.close()

            # Read back and verify
            file_path = Path(temp_dir) / filename
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                read_headers = next(reader)
                assert read_headers == headers

                read_row = next(reader)
                assert read_row[0] == "value1"
                assert read_row[1] == "value2"
                # Verify error message was sanitized
                assert "\n" not in read_row[2]
                assert "duplicate key" in read_row[2]
                assert "DETAIL:" in read_row[2]

    def test_csv_writer_preserves_original_headers(self):
        """Test that original file headers are preserved."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = "test_headers.csv"
            writer = CSVStreamingWriter(filename, temp_dir=temp_dir)

            # Use original headers from a typical import file
            original_headers = ["Họ và tên", "Email", "Số điện thoại"]
            writer.write_header(original_headers)

            row = ["Trần Thị B", "tranthib@example.com", "0123456789"]
            writer.write_row(row)
            writer.close()

            # Read back and verify headers are preserved
            file_path = Path(temp_dir) / filename
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                read_headers = next(reader)
                assert read_headers == original_headers
