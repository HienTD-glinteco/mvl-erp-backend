"""Utility functions for mapping contract types to employee types."""

import json
import logging
import re
import unicodedata
from typing import Any

from apps.hrm.constants import EmployeeType

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text by removing accents and converting to lowercase.

    This function performs accent-insensitive normalization:
    - Removes Vietnamese diacritics (e.g., "Chính thức" -> "chinh thuc")
    - Converts to lowercase
    - Strips whitespace
    - Normalizes multiple spaces to single space

    Args:
        text: The text to normalize.

    Returns:
        Normalized lowercase text without accents.
    """
    if not text:
        return ""

    # Normalize Unicode to decomposed form (separates base chars from accents)
    normalized = unicodedata.normalize("NFD", str(text))

    # Remove combining diacritical marks (accents)
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )

    # Convert to lowercase and strip
    result = without_accents.lower().strip()

    # Normalize multiple spaces to single space
    result = re.sub(r"\s+", " ", result)

    return result


# Default mapping from contract type names to employee type values
# Keys are normalized (lowercase, accent-removed) versions of contract type names
DEFAULT_CONTRACT_TYPE_TO_EMPLOYEE_TYPE_MAPPING: dict[str, str] = {
    # Official / Full-time
    "chinh thuc": EmployeeType.OFFICIAL,
    "official": EmployeeType.OFFICIAL,
    "nhan vien chinh thuc": EmployeeType.OFFICIAL,
    "full time": EmployeeType.OFFICIAL,
    "fulltime": EmployeeType.OFFICIAL,
    # Apprentice
    "hoc viec": EmployeeType.APPRENTICE,
    "apprentice": EmployeeType.APPRENTICE,
    "nhan vien hoc viec": EmployeeType.APPRENTICE,
    # Unpaid - Official
    "nghi khong luong": EmployeeType.UNPAID_OFFICIAL,
    "unpaid official": EmployeeType.UNPAID_OFFICIAL,
    "nghi khong luong chinh thuc": EmployeeType.UNPAID_OFFICIAL,
    # Unpaid - Probation
    "nghi khong luong thu viec": EmployeeType.UNPAID_PROBATION,
    "unpaid probation": EmployeeType.UNPAID_PROBATION,
    # Probation
    "thu viec": EmployeeType.PROBATION,
    "probation": EmployeeType.PROBATION,
    "nhan vien thu viec": EmployeeType.PROBATION,
    # Intern
    "thuc tap": EmployeeType.INTERN,
    "intern": EmployeeType.INTERN,
    "thuc tap sinh": EmployeeType.INTERN,
    # Probation Type 1
    "thu viec loai 1": EmployeeType.PROBATION_TYPE_1,
    "probation type 1": EmployeeType.PROBATION_TYPE_1,
}


def get_employee_type_mapping(custom_mapping: dict[str, str] | None = None) -> dict[str, str]:
    """Get the combined mapping of contract types to employee types.

    Args:
        custom_mapping: Optional custom mapping to override/extend the defaults.
            Keys can be contract type names, slugs, or stringified PKs.
            Values must be uppercase employee_type keys.

    Returns:
        Combined mapping dictionary with normalized keys.
    """
    # Start with default mapping
    mapping = DEFAULT_CONTRACT_TYPE_TO_EMPLOYEE_TYPE_MAPPING.copy()

    # Apply custom mapping if provided
    if custom_mapping:
        for key, value in custom_mapping.items():
            # Normalize the key
            normalized_key = normalize_text(key)
            # Validate the value is a valid EmployeeType
            if value in [choice[0] for choice in EmployeeType.choices]:
                mapping[normalized_key] = value
            else:
                logger.warning(f"Invalid employee_type value in custom mapping: {value}")

    return mapping


def map_contract_type_to_employee_type(
    contract_type_name: str | None,
    contract_type_pk: int | None = None,
    custom_mapping: dict[str, str] | None = None,
    pk_mapping: dict[int, str] | None = None,
) -> tuple[str | None, bool]:
    """Map a contract type to an employee type value.

    Resolution order:
    1. If PK is provided and pk_mapping contains it, use that mapping.
    2. Otherwise, normalize the name and look it up in the name-based mapping.
    3. If not found, return None and False.

    Args:
        contract_type_name: The contract type name to map.
        contract_type_pk: Optional contract type primary key.
        custom_mapping: Optional custom name-based mapping.
        pk_mapping: Optional PK-based mapping (dict of int PK to employee_type).

    Returns:
        Tuple of (employee_type_value or None, was_mapped: bool).
    """
    # Try PK mapping first
    if contract_type_pk is not None and pk_mapping:
        if contract_type_pk in pk_mapping:
            return pk_mapping[contract_type_pk], True

    # Try name mapping
    if contract_type_name:
        mapping = get_employee_type_mapping(custom_mapping)
        normalized_name = normalize_text(contract_type_name)

        if normalized_name in mapping:
            return mapping[normalized_name], True

        # Log unmapped value for review
        logger.debug(f"Unmapped contract type: '{contract_type_name}' (normalized: '{normalized_name}')")

    return None, False


def suggest_employee_type(contract_type_name: str) -> str | None:
    """Suggest an employee type based on partial matching.

    Uses heuristics to suggest a mapping when exact match fails.

    Args:
        contract_type_name: The contract type name to analyze.

    Returns:
        Suggested employee_type value or None.
    """
    if not contract_type_name:
        return None

    normalized = normalize_text(contract_type_name)

    # Heuristic matching based on keywords
    if "chinh thuc" in normalized or "official" in normalized:
        return EmployeeType.OFFICIAL
    if "hoc viec" in normalized or "apprentice" in normalized:
        return EmployeeType.APPRENTICE
    if "thu viec" in normalized or "probation" in normalized:
        if "loai 1" in normalized or "type 1" in normalized:
            return EmployeeType.PROBATION_TYPE_1
        return EmployeeType.PROBATION
    if "thuc tap" in normalized or "intern" in normalized:
        return EmployeeType.INTERN
    if "nghi khong luong" in normalized or "unpaid" in normalized:
        if "thu viec" in normalized or "probation" in normalized:
            return EmployeeType.UNPAID_PROBATION
        return EmployeeType.UNPAID_OFFICIAL

    return None


def load_custom_mapping_from_file(file_path: str) -> dict[str, Any] | None:
    """Load custom mapping from a JSON file.

    Args:
        file_path: Path to the JSON mapping file.

    Returns:
        Dictionary with mapping data or None if loading fails.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load custom mapping from {file_path}: {e}")
        return None
