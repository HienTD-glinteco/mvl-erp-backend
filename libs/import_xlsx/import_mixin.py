"""
Mixin for adding XLSX import functionality to DRF ViewSets.

This module provides a reusable ImportXLSXMixin that adds a universal import action
to any DRF ViewSet, enabling data import from Excel files (.xlsx) into Django models.
"""

import logging
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .import_constants import (
    ERROR_EMPTY_FILE,
    ERROR_INVALID_FILE_TYPE,
    ERROR_NO_FILE,
    SUCCESS_IMPORT_COMPLETE,
)

logger = logging.getLogger(__name__)


class ImportXLSXMixin:
    """
    Mixin for DRF ViewSets to add XLSX import functionality.

    This mixin provides a universal `/import/` action that accepts XLSX files,
    maps columns to model fields, validates data, and performs bulk create/update.

    By default, validation is done at the model level (using model.full_clean()).
    This allows importing all model fields including read-only or auto-generated ones.
    
    If you need serializer-level validation, override get_import_serializer_class()
    to return a custom import serializer without read-only field restrictions.

    Example 1 - Basic import with model-level validation:
        class ProjectViewSet(ImportXLSXMixin, ModelViewSet):
            queryset = Project.objects.all()
            serializer_class = ProjectSerializer

    Example 2 - Custom import schema:
        class ProjectViewSet(ImportXLSXMixin, ModelViewSet):
            queryset = Project.objects.all()
            serializer_class = ProjectSerializer

            def get_import_schema(self, request, file):
                return {
                    "fields": ["name", "start_date", "budget"],
                    "required": ["name"],
                }

    Example 3 - Custom import serializer for validation:
        class ProjectImportSerializer(serializers.ModelSerializer):
            class Meta:
                model = Project
                fields = ["name", "code", "budget"]
                # No read-only fields, all can be imported

        class ProjectViewSet(ImportXLSXMixin, ModelViewSet):
            queryset = Project.objects.all()
            serializer_class = ProjectSerializer

            def get_import_serializer_class(self):
                return ProjectImportSerializer
    """

    @extend_schema(
        summary="Import data from XLSX",
        description="Import model instances from an Excel (.xlsx) file",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "format": "binary",
                        "description": "XLSX file to import",
                    },
                },
                "required": ["file"],
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success_count": {"type": "integer"},
                    "error_count": {"type": "integer"},
                    "errors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "row": {"type": "integer"},
                                "errors": {"type": "object"},
                            },
                        },
                    },
                },
            },
            400: {"description": "Bad request"},
        },
        parameters=[
            OpenApiParameter(
                name="file",
                type={"type": "string", "format": "binary"},
                location=OpenApiParameter.QUERY,
                description="XLSX file to import",
                required=True,
            )
        ],
    )
    @action(detail=False, methods=["post"])
    def import_data(self, request: Request) -> Response:
        """
        Import data from XLSX file.

        This action:
        1. Validates the uploaded file
        2. Loads the import schema (auto or custom)
        3. Parses and validates each row
        4. Bulk creates/updates model instances
        5. Returns import summary with errors
        """
        # Validate file upload
        if "file" not in request.FILES:
            return Response(
                {"detail": _(ERROR_NO_FILE)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file = request.FILES["file"]

        # Check file extension
        if not file.name.endswith(".xlsx"):
            return Response(
                {"detail": _(ERROR_INVALID_FILE_TYPE)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Load import schema
            import_schema = self.get_import_schema(request, file)

            # Parse and validate data
            parsed_data, errors = self._parse_xlsx_file(file, import_schema)

            if not parsed_data and not errors:
                return Response(
                    {"detail": _(ERROR_EMPTY_FILE)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Import data
            success_count = 0
            if parsed_data:
                success_count = self._bulk_import(parsed_data, import_schema, errors)

            return Response(
                {
                    "success_count": success_count,
                    "error_count": len(errors),
                    "errors": errors,
                    "detail": _(SUCCESS_IMPORT_COMPLETE),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception(f"Import failed: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get_import_schema(self, request: Request, file: Any) -> dict:
        """
        Get the import schema for mapping columns to fields.

        Override this method to customize the import schema.
        By default, auto-generates schema from model fields.

        Args:
            request: The HTTP request
            file: The uploaded file

        Returns:
            dict: Import schema with keys:
                - fields: List of field names to import
                - required: List of required field names
                - validators: Optional dict of field validators
        """
        return self._auto_generate_schema()

    def get_import_serializer_class(self):
        """
        Get the serializer class to use for import validation.

        Override this method to use a different serializer for imports
        than for regular CRUD operations. This is useful when the regular
        serializer has read-only fields (like auto-generated codes) or
        required fields (like relations) that should not be required for imports.

        Returns:
            Serializer class or None to skip serializer validation
        """
        return None  # By default, use model-level validation only

    def _auto_generate_schema(self) -> dict:
        """
        Auto-generate import schema from model fields.

        Ignores fields like id, created_at, updated_at, and AutoFields.

        Returns:
            dict: Auto-generated import schema
        """
        from django.db import models

        from .import_constants import IGNORED_FIELD_NAMES

        model = self.queryset.model
        fields = []
        required = []

        for field in model._meta.get_fields():
            # Skip ignored fields
            if field.name in IGNORED_FIELD_NAMES:
                continue

            # Skip auto fields
            if isinstance(field, (models.AutoField, models.BigAutoField)):
                continue

            # Skip reverse relations
            if field.many_to_many or field.one_to_many or field.one_to_one:
                continue

            # Add field to schema
            fields.append(field.name)

            # Check if field is required
            if hasattr(field, "blank") and not field.blank and not field.null:
                required.append(field.name)

        return {
            "fields": fields,
            "required": required,
        }

    def _parse_xlsx_file(self, file: Any, schema: dict) -> tuple[list[dict], list[dict]]:
        """
        Parse XLSX file and validate data.

        Args:
            file: The uploaded XLSX file
            schema: Import schema

        Returns:
            tuple: (parsed_data, errors)
                - parsed_data: List of validated dictionaries
                - errors: List of error dictionaries with row numbers
        """
        parsed_data = []
        errors = []

        try:
            workbook = load_workbook(file, read_only=True)
            sheet = workbook.active

            # Get header row
            headers = self._extract_headers(sheet)

            # Map headers to fields
            field_mapping = self._map_headers_to_fields(headers, schema["fields"])

            # Parse data rows
            for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                # Skip empty rows
                if not any(row):
                    continue

                # Process single row
                row_data, row_errors = self._process_row(row, headers, field_mapping, schema)

                if row_errors:
                    errors.append({"row": row_idx, "errors": row_errors})
                elif row_data:
                    parsed_data.append(row_data)

            workbook.close()

        except Exception as e:
            logger.exception(f"Error parsing XLSX file: {e}")
            errors.append({"row": 0, "errors": {"_general": str(e)}})

        return parsed_data, errors

    def _extract_headers(self, sheet: Any) -> list[str]:
        """
        Extract header row from worksheet.

        Args:
            sheet: Worksheet object

        Returns:
            list: List of header names
        """
        headers = []
        for cell in sheet[1]:
            if cell.value:
                headers.append(str(cell.value).strip())
        return headers

    def _process_row(
        self, row: tuple, headers: list[str], field_mapping: dict, schema: dict
    ) -> tuple[dict | None, dict]:
        """
        Process a single row of data.

        Args:
            row: Tuple of cell values
            headers: List of header names
            field_mapping: Mapping of headers to field names
            schema: Import schema

        Returns:
            tuple: (validated_data, errors)
        """
        row_data = {}
        row_errors = {}

        # Map cells to fields
        for col_idx, cell_value in enumerate(row):
            if col_idx < len(headers):
                field_name = field_mapping.get(headers[col_idx])
                if field_name:
                    row_data[field_name] = cell_value

        # Validate required fields
        for required_field in schema.get("required", []):
            if not row_data.get(required_field):
                row_errors[required_field] = _("This field is required")

        # Validate data using import serializer if provided
        if not row_errors:
            serializer_class = self.get_import_serializer_class()
            
            if serializer_class:
                # Use import-specific serializer for validation
                try:
                    serializer = serializer_class(data=row_data)
                    if serializer.is_valid():
                        return serializer.validated_data, {}
                    else:
                        row_errors.update(serializer.errors)
                except Exception as e:
                    row_errors["_general"] = str(e)
            else:
                # No import serializer - use model-level validation only
                # Just return the raw data, validation will happen at model.full_clean()
                return row_data, {}

        return None, row_errors

    def _map_headers_to_fields(self, headers: list[str], fields: list[str]) -> dict:
        """
        Map Excel headers to model field names.

        Performs case-insensitive matching and handles spaces/underscores.

        Args:
            headers: List of column headers from Excel
            fields: List of valid field names from schema

        Returns:
            dict: Mapping of header to field name
        """
        mapping = {}
        field_lookup = {field.lower().replace("_", " "): field for field in fields}

        for header in headers:
            normalized_header = header.lower().replace("_", " ")
            if normalized_header in field_lookup:
                mapping[header] = field_lookup[normalized_header]
            elif header in fields:
                mapping[header] = header

        return mapping

    def _bulk_import(self, data: list[dict], schema: dict, errors: list[dict]) -> int:
        """
        Bulk import validated data into database.

        Args:
            data: List of validated data dictionaries
            schema: Import schema
            errors: List to append errors to

        Returns:
            int: Number of successfully imported records
        """
        model = self.queryset.model
        success_count = 0

        try:
            with transaction.atomic():
                for item_data in data:
                    try:
                        # Create model instance
                        instance = model(**item_data)
                        instance.full_clean()
                        instance.save()
                        success_count += 1

                        # Log audit event if audit logging is enabled
                        self._log_import_audit(instance)

                    except Exception as e:
                        logger.warning(f"Failed to import row: {e}")
                        errors.append(
                            {
                                "row": success_count + len(errors) + 2,
                                "errors": {"_general": str(e)},
                            }
                        )

        except Exception as e:
            logger.exception(f"Bulk import failed: {e}")
            raise

        return success_count

    def _log_import_audit(self, instance: Any) -> None:
        """
        Log audit event for imported instance.

        Only logs if audit logging is available and enabled.

        Args:
            instance: The imported model instance
        """
        try:
            from apps.audit_logging import LogAction, log_audit_event

            request = self.request if hasattr(self, "request") else None
            log_audit_event(
                action=LogAction.IMPORT,
                modified_object=instance,
                user=request.user if request and hasattr(request, "user") else None,
                request=request,
            )
        except ImportError:
            # Audit logging not available
            pass
        except Exception as e:
            logger.warning(f"Failed to log audit event: {e}")
