"""
Mixin for adding XLSX import functionality to DRF ViewSets.

This module provides a reusable ImportXLSXMixin that adds a universal import action
to any DRF ViewSet, enabling data import from Excel files (.xlsx) into Django models.
"""

import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .error_report import ErrorReportGenerator
from .import_constants import (
    ERROR_ASYNC_NOT_ENABLED,
    ERROR_EMPTY_FILE,
    ERROR_FOREIGN_KEY_NOT_FOUND,
    ERROR_INVALID_FILE_TYPE,
    ERROR_NO_FILE,
    SUCCESS_IMPORT_COMPLETE,
    SUCCESS_PREVIEW_COMPLETE,
)
from .serializers import ImportAsyncResponseSerializer, ImportPreviewResponseSerializer, ImportResultSerializer
from .storage import get_storage_backend
from .tasks import import_xlsx_task

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

    queryset: QuerySet[Any]

    @extend_schema(
        summary="Import data from XLSX",
        description="Import model instances from an Excel (.xlsx) file. "
        "Supports async processing, preview mode, and error report download.",
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
        parameters=[
            OpenApiParameter(
                name="async",
                description="If 'true', process import in background using Celery (requires IMPORTER_CELERY_ENABLED=true)",
                required=False,
                type=bool,
            ),
            OpenApiParameter(
                name="preview",
                description="If 'true', validate data without saving (dry-run mode)",
                required=False,
                type=bool,
            ),
        ],
        responses={
            200: ImportResultSerializer,
            202: ImportAsyncResponseSerializer,
            400: OpenApiResponse(description="Bad request"),
        },
    )
    @action(detail=False, methods=["post"])
    def import_data(self, request: Request) -> Response:
        """
        Import data from XLSX file.

        Query parameters:
            async: If 'true', process in background (requires Celery)
            preview: If 'true', validate without saving (dry-run)

        This action:
        1. Validates the uploaded file
        2. Loads the import schema (auto or custom)
        3. Parses and validates each row
        4. (If not preview) Bulk creates/updates model instances
        5. Returns import summary with errors
        6. (If errors) Optionally generates error report XLSX

        Returns:
            - Synchronous (200): Import results with error details
            - Asynchronous (202): Task ID and status information
            - Preview (200): Validation results without saving
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

        # Check for async mode
        use_async = request.query_params.get("async", "false").lower() == "true"
        celery_enabled = getattr(settings, "IMPORTER_CELERY_ENABLED", False)

        if use_async and not celery_enabled:
            return Response(
                {"error": _(ERROR_ASYNC_NOT_ENABLED)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for preview mode
        preview_mode = request.query_params.get("preview", "false").lower() == "true"

        try:
            # Load import schema
            import_schema = self.get_import_schema(request, file)

            if use_async and not preview_mode:
                # Handle async import
                return self._handle_async_import(request, file, import_schema)

            # Parse and validate data
            parsed_data, errors, original_data, headers = self._parse_xlsx_file_with_original(file, import_schema)

            if not parsed_data and not errors:
                return Response(
                    {"detail": _(ERROR_EMPTY_FILE)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if preview_mode:
                # Preview mode - don't save, just return validation results
                return self._handle_preview(parsed_data, errors)

            # Import data
            success_count = 0
            if parsed_data:
                success_count = self._bulk_import(parsed_data, import_schema, errors)

            # Generate error report if errors exist
            error_file_url = None
            if errors:
                error_file_url = self._generate_error_report(errors, original_data, headers)

            response_data = {
                "success_count": success_count,
                "error_count": len(errors),
                "errors": errors[:100],  # Limit errors in response
                "detail": _(SUCCESS_IMPORT_COMPLETE),
            }

            if error_file_url:
                response_data["error_file_url"] = error_file_url

            return Response(response_data, status=status.HTTP_200_OK)

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

    def _handle_async_import(self, request: Request, file: Any, schema: dict) -> Response:
        """
        Handle async import using Celery.

        Args:
            request: HTTP request
            file: Uploaded file
            schema: Import schema

        Returns:
            Response: Async task information
        """
        # Save file temporarily
        storage = get_storage_backend()
        file_content = file.read()
        file_path = storage.save_temp_file(file_content, file.name)

        # Get model info
        model = self.queryset.model
        app_label = model._meta.app_label
        model_name = model.__name__

        # Get user ID for audit logging
        user_id = request.user.id if hasattr(request, "user") and request.user.is_authenticated else None

        # Trigger background task
        task = import_xlsx_task.delay(app_label, model_name, file_path, schema, user_id)

        return Response(
            {
                "task_id": task.id,
                "status": "PENDING",
                "message": _("Import task has been queued for processing"),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    def _handle_preview(self, parsed_data: list[dict], errors: list[dict]) -> Response:
        """
        Handle preview mode (dry-run).

        Args:
            parsed_data: Validated data
            errors: Validation errors

        Returns:
            Response: Preview results
        """
        max_preview = getattr(settings, "IMPORTER_MAX_PREVIEW_ROWS", 10)
        preview_data = parsed_data[:max_preview] if parsed_data else []

        return Response(
            {
                "valid_count": len(parsed_data),
                "invalid_count": len(errors),
                "errors": errors[:100],  # Limit errors in response
                "preview_data": preview_data[:10],  # Show first 10 valid rows
                "detail": _(SUCCESS_PREVIEW_COMPLETE),
            },
            status=status.HTTP_200_OK,
        )

    def _generate_error_report(self, errors: list[dict], original_data: list[list], headers: list[str]) -> str:
        """
        Generate error report XLSX file.

        Args:
            errors: List of errors
            original_data: Original data rows
            headers: Column headers

        Returns:
            str: URL to download error report
        """
        try:
            generator = ErrorReportGenerator()
            report_content = generator.generate(errors, original_data, headers)

            # Save to storage
            storage = get_storage_backend()
            file_path = storage.save_error_report(report_content)

            # Get URL
            return storage.get_url(file_path)

        except Exception as e:
            logger.warning(f"Failed to generate error report: {e}")
            return None

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
        parsed_data, errors, _, _ = self._parse_xlsx_file_with_original(file, schema)
        return parsed_data, errors

    def _parse_xlsx_file_with_original(
        self, file: Any, schema: dict
    ) -> tuple[list[dict], list[dict], list[list], list[str]]:
        """
        Parse XLSX file and validate data, keeping original data for error reports.

        Args:
            file: The uploaded XLSX file
            schema: Import schema

        Returns:
            tuple: (parsed_data, errors, original_data, headers)
                - parsed_data: List of validated dictionaries
                - errors: List of error dictionaries with row numbers
                - original_data: Original data rows (for error reporting)
                - headers: Column headers
        """
        parsed_data = []
        errors = []
        original_data = []
        headers = []

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

                # Store original row data
                original_data.append(list(row))

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

        return parsed_data, errors, original_data, headers

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

    def _resolve_foreign_key(self, field, value: Any) -> Any:
        """
        Resolve ForeignKey value.

        Args:
            field: Django ForeignKey field
            value: Value from Excel (can be ID, natural key, or string)

        Returns:
            Related model instance or None

        Raises:
            ValueError: If related object not found
        """
        if value is None or value == "":
            return None

        related_model = field.related_model

        # Try to find by primary key first
        try:
            if isinstance(value, (int, float)):
                return related_model.objects.get(pk=int(value))
        except (related_model.DoesNotExist, ValueError):
            pass

        # Try to find by common natural keys (name, code, email, username)
        for lookup_field in ["name", "code", "email", "username"]:
            if hasattr(related_model, lookup_field):
                try:
                    return related_model.objects.get(**{lookup_field: str(value)})
                except related_model.DoesNotExist:
                    continue

        # Try __str__ match as last resort
        try:
            return related_model.objects.get(**{f"{lookup_field}__iexact": str(value)})
        except:
            pass

        raise ValueError(_(ERROR_FOREIGN_KEY_NOT_FOUND).format(field=field.name, value=value))

    def _resolve_many_to_many(self, field, value: Any) -> list:
        """
        Resolve ManyToMany values.

        Args:
            field: Django ManyToManyField
            value: Comma-separated string of IDs or names

        Returns:
            List of related model instances
        """
        if value is None or value == "":
            return []

        related_model = field.related_model
        values = [v.strip() for v in str(value).split(",") if v.strip()]
        instances = []

        for val in values:
            try:
                # Try to find by primary key first
                try:
                    if val.isdigit():
                        instances.append(related_model.objects.get(pk=int(val)))
                        continue
                except (related_model.DoesNotExist, ValueError):
                    pass

                # Try natural keys
                for lookup_field in ["name", "code", "email", "username"]:
                    if hasattr(related_model, lookup_field):
                        try:
                            instances.append(related_model.objects.get(**{lookup_field: val}))
                            break
                        except related_model.DoesNotExist:
                            continue

            except Exception:
                logger.warning(f"Could not resolve {field.name} value: {val}")

        return instances

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
        from django.db import models

        row_data = {}
        row_errors = {}
        m2m_data = {}  # Store ManyToMany data separately

        model = self.queryset.model

        # Map cells to fields
        for col_idx, cell_value in enumerate(row):
            if col_idx < len(headers):
                field_name = field_mapping.get(headers[col_idx])
                if field_name:
                    # Check if this is a relational field
                    try:
                        model_field = model._meta.get_field(field_name)

                        if isinstance(model_field, models.ForeignKey):
                            # Resolve ForeignKey
                            try:
                                row_data[field_name] = self._resolve_foreign_key(model_field, cell_value)
                            except ValueError as e:
                                row_errors[field_name] = str(e)
                        elif isinstance(model_field, models.ManyToManyField):
                            # Store ManyToMany for later (after instance creation)
                            m2m_data[field_name] = self._resolve_many_to_many(model_field, cell_value)
                        else:
                            # Regular field
                            row_data[field_name] = cell_value
                    except:
                        # Field not found in model, just store as-is
                        row_data[field_name] = cell_value

        # Store M2M data for later use
        if m2m_data:
            row_data["_m2m_data"] = m2m_data

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
                        # Extract M2M data if present
                        m2m_data = item_data.pop("_m2m_data", {})

                        # Create model instance
                        instance = model(**item_data)
                        instance.full_clean()
                        instance.save()

                        # Set ManyToMany relationships
                        for field_name, related_objects in m2m_data.items():
                            getattr(instance, field_name).set(related_objects)

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
