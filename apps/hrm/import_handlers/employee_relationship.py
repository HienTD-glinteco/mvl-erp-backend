"""Import handler for Employee Relationship."""

import logging
from datetime import date, datetime
from typing import Any

from django.db import transaction

from apps.hrm.constants import RelationType
from apps.hrm.models import Employee, EmployeeRelationship
from libs.strings import normalize_header

logger = logging.getLogger(__name__)

# Column mapping for import template (Vietnamese headers to field names)
COLUMN_MAPPING = {
    "stt": "row_number",
    "mã nhân viên": "employee_code",
    "tên nhân viên": "employee_name",
    "tên người thân": "relative_name",
    "mối quan hệ": "relation_type",
    "ngày sinh": "date_of_birth",
    "số cmnd/cccd/giấy khai sinh": "citizen_id",
    "mã số thuế": "tax_code",
    "địa chỉ": "address",
    "số điện thoại": "phone",
    "nghề nghiệp": "occupation",
    "ghi chú": "note",
}

# Relation type mapping (Vietnamese labels to RelationType values)
RELATION_TYPE_MAPPING = {
    "con": RelationType.CHILD,
    "vợ": RelationType.WIFE,
    "chồng": RelationType.HUSBAND,
    "bố": RelationType.FATHER,
    "cha": RelationType.FATHER,
    "mẹ": RelationType.MOTHER,
    "anh": RelationType.BROTHER,
    "em trai": RelationType.BROTHER,
    "chị": RelationType.SISTER,
    "em gái": RelationType.SISTER,
    "anh chị em": RelationType.SIBLING,
    "ông nội": RelationType.GRANDFATHER,
    "ông ngoại": RelationType.GRANDFATHER,
    "ông": RelationType.GRANDFATHER,
    "bà nội": RelationType.GRANDMOTHER,
    "bà ngoại": RelationType.GRANDMOTHER,
    "bà": RelationType.GRANDMOTHER,
    "khác": RelationType.OTHER,
}


def normalize_value(value: Any) -> str:
    """Normalize cell value by converting to string and stripping."""
    if value is None:
        return ""
    return str(value).strip()


def parse_date_field(value: Any, field_name: str) -> tuple[date | None, str | None]:
    """
    Parse date from various formats.

    Args:
        value: Date value (string, date, or datetime)
        field_name: Name of field for error messages

    Returns:
        Tuple of (date_object, error_message)
    """
    if value is None or str(value).strip() == "":
        return None, None

    # If already a date object
    if isinstance(value, date):
        return value, None

    # If datetime object, extract date
    if isinstance(value, datetime):
        return value.date(), None

    # Try parsing string formats
    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ]

    value_str = str(value).strip()
    for fmt in date_formats:
        try:
            return datetime.strptime(value_str, fmt).date(), None
        except ValueError:
            continue

    return None, f"Invalid date format for {field_name}: {value}"


def parse_relation_type(value: Any) -> tuple[str | None, str | None]:
    """
    Parse relation type from Vietnamese label or English value.

    Args:
        value: Relation type value (Vietnamese label or enum value)

    Returns:
        Tuple of (relation_type_value, error_message)
    """
    if value is None or str(value).strip() == "":
        return None, "Relation type is required"

    value_str = normalize_value(value).lower()

    # Try mapping from Vietnamese label
    if value_str in RELATION_TYPE_MAPPING:
        return RELATION_TYPE_MAPPING[value_str], None

    # Try direct enum value match (uppercase)
    value_upper = value_str.upper()
    valid_values = [choice.value for choice in RelationType]
    if value_upper in valid_values:
        return value_upper, None

    return None, f"Invalid relation type: {value}. Valid values: {', '.join(valid_values)}"


def _validate_required_fields(
    employee_code: str,
    relative_name: str,
    relation_type_raw: Any,
) -> tuple[str | None, str | None]:
    """Validate required fields and parse relation type.

    Returns:
        Tuple of (relation_type, error_message)
    """
    if not employee_code:
        return None, "Employee code is required"

    if not relative_name:
        return None, "Relative name is required"

    return parse_relation_type(relation_type_raw)


def _validate_citizen_id(citizen_id: str) -> tuple[str, str | None]:
    """Validate and clean citizen ID.

    Returns:
        Tuple of (cleaned_citizen_id, error_message)
    """
    if not citizen_id:
        return "", None

    # Remove any non-digit characters for validation
    citizen_id_clean = "".join(c for c in citizen_id if c.isdigit())
    if citizen_id_clean and len(citizen_id_clean) not in (9, 12):
        return "", f"Invalid citizen ID length: {len(citizen_id_clean)}. Must be 9 or 12 digits."

    return citizen_id_clean, None


def _create_or_update_relationship(
    employee: Employee,
    relative_name: str,
    relation_type: str,
    relationship_data: dict,
) -> tuple[EmployeeRelationship, str]:
    """Create or update employee relationship.

    Returns:
        Tuple of (relationship, action)
    """
    existing_relationship = EmployeeRelationship.objects.filter(
        employee=employee,
        relative_name__iexact=relative_name,
        relation_type=relation_type,
    ).first()

    with transaction.atomic():
        if existing_relationship:
            # Update existing relationship
            for key, value in relationship_data.items():
                setattr(existing_relationship, key, value)
            existing_relationship.save()
            relationship = existing_relationship
            action = "updated"
            logger.info(f"Updated relationship {relationship.code} - {relationship.relative_name} for {employee.code}")
        else:
            # Create new relationship
            relationship_data["employee"] = employee
            relationship = EmployeeRelationship.objects.create(**relationship_data)
            action = "created"
            logger.info(f"Created relationship {relationship.code} - {relationship.relative_name} for {employee.code}")

    return relationship, action


def import_handler(
    row: list,
    row_index: int,
    headers: list,
    cache: dict | None = None,
    **kwargs: Any,
) -> dict:
    """
    Import handler for EmployeeRelationship model.

    Args:
        row: List of cell values for this row
        row_index: 1-based index of the row being processed
        headers: List of column headers from the first row
        cache: Shared cache dictionary for lookups (optional)
        **kwargs: Additional context (user, etc.)

    Returns:
        Result dictionary with:
        - ok: Boolean indicating success
        - error: Error message if failed
        - row_index: Row index for reference
        - action: "created" or "updated"
        - result: Created/updated object details
    """
    try:
        # Initialize cache if not provided
        if cache is None:
            cache = {}

        # STEP 1: Normalize Headers and Map to Values
        row_data = _extract_row_data(row, headers)

        # STEP 2: Extract and Validate Required Fields
        employee_code = normalize_value(row_data.get("employee_code"))
        relative_name = normalize_value(row_data.get("relative_name"))
        relation_type_raw = row_data.get("relation_type")

        # Validate required fields and parse relation type
        relation_type, validation_error = _validate_required_fields(employee_code, relative_name, relation_type_raw)
        if validation_error:
            return {"ok": False, "error": validation_error}

        # STEP 3: Find Employee
        employee = Employee.objects.filter(code=employee_code).first()
        if not employee:
            return {"ok": False, "error": f"Employee with code '{employee_code}' not found"}

        # STEP 4: Parse and Validate Optional Fields
        date_of_birth, date_error = parse_date_field(row_data.get("date_of_birth"), "date_of_birth")
        if date_error:
            return {"ok": False, "error": date_error}

        citizen_id, citizen_error = _validate_citizen_id(normalize_value(row_data.get("citizen_id")))
        if citizen_error:
            return {"ok": False, "error": citizen_error}

        # STEP 5: Build relationship data and create/update
        relationship_data = {
            "relative_name": relative_name,
            "relation_type": relation_type,
            "date_of_birth": date_of_birth,
            "citizen_id": citizen_id,
            "tax_code": normalize_value(row_data.get("tax_code")),
            "address": normalize_value(row_data.get("address")),
            "phone": normalize_value(row_data.get("phone")),
            "occupation": normalize_value(row_data.get("occupation")),
            "note": normalize_value(row_data.get("note")),
            "is_active": True,
        }

        relationship, action = _create_or_update_relationship(
            employee,
            relative_name,
            relation_type,  # type: ignore
            relationship_data,
        )

        # STEP 6: Return Success Result
        return {
            "ok": True,
            "row_index": row_index,
            "action": action,
            "result": {
                "relationship_id": str(relationship.id),
                "relationship_code": relationship.code,
                "employee_code": employee.code,
                "relative_name": relationship.relative_name,
                "relation_type": relationship.relation_type,
            },
        }

    except Exception as e:
        logger.exception(f"Import handler error at row {row_index}: {e}")
        return {
            "ok": False,
            "error": str(e),
        }


def _extract_row_data(row: list, headers: list) -> dict:
    """Extract row data by mapping headers to field names."""
    normalized_headers = [normalize_header(h) for h in headers]
    row_data = {}
    for i, header in enumerate(normalized_headers):
        if header in COLUMN_MAPPING:
            field_name = COLUMN_MAPPING[header]
            row_data[field_name] = row[i] if i < len(row) else None
    return row_data
