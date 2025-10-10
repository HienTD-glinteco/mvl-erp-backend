"""
Shared utility functions for XLSX import processing.

This module contains common logic used by both the synchronous import mixin
and the asynchronous Celery task to avoid code duplication.
"""

import logging
from typing import Any

from django.db import models as django_models
from django.utils.translation import gettext as _

from .import_constants import ERROR_FOREIGN_KEY_NOT_FOUND

logger = logging.getLogger(__name__)


def map_headers_to_fields(headers: list[str], fields: list[str]) -> dict:
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


def resolve_foreign_key(field, value: Any) -> Any:
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


def resolve_many_to_many(field, value: Any) -> list:
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

        except Exception as e:
            logger.warning(f"Could not resolve value: {val} - {e}")

    return instances


def process_row(row: tuple, headers: list[str], field_mapping: dict, schema: dict, model) -> tuple[dict | None, dict]:
    """
    Process a single row of data.

    Args:
        row: Tuple of cell values
        headers: List of header names
        field_mapping: Mapping of headers to field names
        schema: Import schema
        model: Django model class

    Returns:
        tuple: (validated_data, errors)
    """
    row_data = {}
    row_errors = {}
    m2m_data = {}  # Store ManyToMany data separately

    # Map cells to fields
    for col_idx, cell_value in enumerate(row):
        if col_idx < len(headers):
            field_name = field_mapping.get(headers[col_idx])
            if field_name:
                # Check if this is a relational field
                try:
                    model_field = model._meta.get_field(field_name)

                    if isinstance(model_field, django_models.ForeignKey):
                        # Resolve ForeignKey
                        try:
                            row_data[field_name] = resolve_foreign_key(model_field, cell_value)
                        except ValueError as e:
                            row_errors[field_name] = str(e)
                    elif isinstance(model_field, django_models.ManyToManyField):
                        # Store ManyToMany for later (after instance creation)
                        m2m_data[field_name] = resolve_many_to_many(model_field, cell_value)
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

    if row_errors:
        return None, row_errors

    return row_data, {}


def extract_headers(sheet: Any) -> list[str]:
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


def bulk_import_data(model, data: list[dict], errors: list[dict], user_id=None, request=None) -> int:
    """
    Bulk import validated data into database.

    Args:
        model: Django model class
        data: List of validated data dictionaries
        errors: List to append errors to
        user_id: Optional user ID for audit logging
        request: Optional request object for audit logging context

    Returns:
        int: Number of successfully imported records
    """
    from django.db import transaction

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
                    log_import_audit(instance, user_id, request)

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


def log_import_audit(instance, user_id=None, request=None):
    """
    Log audit event for imported instance.

    Args:
        instance: The imported model instance
        user_id: Optional user ID
        request: Optional request object
    """
    try:
        from apps.audit_logging import LogAction, log_audit_event

        user = None
        if user_id and not request:
            # Get user from ID (for async tasks)
            try:
                from apps.core.models import User

                user = User.objects.get(pk=user_id)
            except:
                pass
        elif request and hasattr(request, "user"):
            # Get user from request (for sync imports)
            user = request.user

        log_audit_event(
            action=LogAction.IMPORT,
            modified_object=instance,
            user=user,
            request=request,
        )
    except ImportError:
        # Audit logging not available
        pass
    except Exception as e:
        logger.warning(f"Failed to log audit event: {e}")
