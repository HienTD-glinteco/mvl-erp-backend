"""
XLSX generator for creating Excel files from schema definitions.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .constants import (
    DEFAULT_HEADER_ALIGNMENT,
    DEFAULT_HEADER_BG_COLOR,
    DEFAULT_HEADER_FONT_BOLD,
    DEFAULT_HEADER_FONT_SIZE,
    ERROR_INVALID_SCHEMA,
)


class XLSXGenerator:
    """
    Generator for creating XLSX files from schema definitions.
    """

    def __init__(self):
        """Initialize XLSX generator."""
        self.workbook = None

    def generate(self, schema):
        """
        Generate XLSX file from schema.

        Args:
            schema: Export schema with structure:
                {
                    "sheets": [{
                        "name": str,
                        "headers": [str, ...],
                        "field_names": [str, ...],  # Optional
                        "data": [dict, ...],
                        "groups": [{"title": str, "span": int}, ...],  # Optional
                        "merge_rules": [str, ...]  # Optional
                    }]
                }

        Returns:
            BytesIO: Excel file content
        """
        if not schema or "sheets" not in schema:
            raise ValueError(ERROR_INVALID_SCHEMA)

        self.workbook = Workbook()
        # Remove default sheet
        if "Sheet" in self.workbook.sheetnames:
            del self.workbook["Sheet"]

        # Create each sheet
        for sheet_def in schema["sheets"]:
            self._create_sheet(sheet_def)

        # Save to BytesIO
        output = BytesIO()
        self.workbook.save(output)
        output.seek(0)
        return output

    def _create_sheet(self, sheet_def):
        """
        Create a single sheet from definition.

        Args:
            sheet_def: Sheet definition dictionary
        """
        sheet_name = sheet_def.get("name", "Sheet1")
        headers = sheet_def.get("headers", [])
        field_names = sheet_def.get("field_names", headers)
        data = sheet_def.get("data", [])
        groups = sheet_def.get("groups", [])
        merge_rules = sheet_def.get("merge_rules", [])

        # Create worksheet
        ws = self.workbook.create_sheet(title=sheet_name)

        current_row = 1

        # Add group headers if defined
        if groups:
            current_row = self._add_group_headers(ws, groups, current_row)

        # Add column headers
        current_row = self._add_headers(ws, headers, current_row)

        # Add data rows
        if data:
            current_row = self._add_data_rows(ws, data, field_names, current_row, merge_rules)

        # Auto-size columns
        self._auto_size_columns(ws)

    def _add_group_headers(self, ws, groups, start_row):
        """
        Add grouped headers (multi-level headers).

        Args:
            ws: Worksheet object
            groups: List of group definitions
            start_row: Starting row number

        Returns:
            int: Next row number
        """
        col = 1
        for group in groups:
            title = group.get("title", "")
            span = group.get("span", 1)

            # Write group title
            cell = ws.cell(row=start_row, column=col, value=title)
            cell.font = Font(bold=True, size=DEFAULT_HEADER_FONT_SIZE)
            cell.fill = PatternFill(start_color=DEFAULT_HEADER_BG_COLOR, end_color=DEFAULT_HEADER_BG_COLOR, fill_type="solid")
            cell.alignment = Alignment(horizontal=DEFAULT_HEADER_ALIGNMENT, vertical="center")
            cell.border = self._get_border()

            # Merge cells if span > 1
            if span > 1:
                ws.merge_cells(
                    start_row=start_row,
                    start_column=col,
                    end_row=start_row,
                    end_column=col + span - 1,
                )

            col += span

        return start_row + 1

    def _add_headers(self, ws, headers, start_row):
        """
        Add column headers.

        Args:
            ws: Worksheet object
            headers: List of header strings
            start_row: Starting row number

        Returns:
            int: Next row number
        """
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=start_row, column=col, value=header)
            cell.font = Font(bold=DEFAULT_HEADER_FONT_BOLD, size=DEFAULT_HEADER_FONT_SIZE)
            cell.fill = PatternFill(start_color=DEFAULT_HEADER_BG_COLOR, end_color=DEFAULT_HEADER_BG_COLOR, fill_type="solid")
            cell.alignment = Alignment(horizontal=DEFAULT_HEADER_ALIGNMENT, vertical="center")
            cell.border = self._get_border()

        return start_row + 1

    def _add_data_rows(self, ws, data, field_names, start_row, merge_rules):
        """
        Add data rows to worksheet.

        Args:
            ws: Worksheet object
            data: List of data dictionaries
            field_names: List of field names corresponding to columns
            start_row: Starting row number
            merge_rules: List of field names to merge vertically

        Returns:
            int: Next row number
        """
        if not data:
            return start_row

        # Track merge ranges for each merge rule field
        merge_ranges = {field: [] for field in merge_rules}
        prev_values = {field: None for field in merge_rules}
        merge_start = {field: start_row for field in merge_rules}

        # Write data and track merge ranges
        self._write_data_rows(ws, data, field_names, start_row, merge_rules, merge_ranges, prev_values, merge_start)

        # Record final merge ranges
        self._finalize_merge_ranges(data, field_names, start_row, merge_rules, merge_ranges, merge_start)

        # Apply merges
        self._apply_cell_merges(ws, merge_ranges)

        return start_row + len(data)

    def _write_data_rows(self, ws, data, field_names, start_row, merge_rules, merge_ranges, prev_values, merge_start):
        """Write data to cells and track values for merging."""
        for row_idx, row_data in enumerate(data):
            current_row = start_row + row_idx

            for col, field_name in enumerate(field_names, start=1):
                value = row_data.get(field_name, "")
                cell = ws.cell(row=current_row, column=col, value=value)
                cell.border = self._get_border()

                # Track merge ranges for this field if needed
                if field_name in merge_rules:
                    self._track_merge_value(
                        field_name, value, current_row, col, merge_ranges, prev_values, merge_start
                    )

    def _track_merge_value(self, field_name, current_value, current_row, col, merge_ranges, prev_values, merge_start):
        """Track value changes for cell merging."""
        # If value changed, record merge range for previous value
        if prev_values[field_name] is not None and current_value != prev_values[field_name]:
            if current_row - merge_start[field_name] > 1:
                merge_ranges[field_name].append((merge_start[field_name], current_row - 1, col))
            merge_start[field_name] = current_row

        prev_values[field_name] = current_value

    def _finalize_merge_ranges(self, data, field_names, start_row, merge_rules, merge_ranges, merge_start):
        """Record final merge ranges after all data is written."""
        final_row = start_row + len(data) - 1
        for field_name in merge_rules:
            col = field_names.index(field_name) + 1
            if final_row - merge_start[field_name] >= 1:
                merge_ranges[field_name].append((merge_start[field_name], final_row, col))

    def _apply_cell_merges(self, ws, merge_ranges):
        """Apply cell merges to worksheet."""
        for field_name, ranges in merge_ranges.items():
            for start_r, end_r, col in ranges:
                if end_r > start_r:
                    ws.merge_cells(start_row=start_r, start_column=col, end_row=end_r, end_column=col)
                    # Center align merged cells
                    ws.cell(row=start_r, column=col).alignment = Alignment(horizontal="center", vertical="center")

    def _get_border(self):
        """
        Get default border style.

        Returns:
            Border: Border style object
        """
        thin_border = Side(style="thin", color="000000")
        return Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)

    def _auto_size_columns(self, ws):
        """
        Auto-size columns based on content.

        Args:
            ws: Worksheet object
        """
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)

            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass

            # Set column width (add padding)
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
