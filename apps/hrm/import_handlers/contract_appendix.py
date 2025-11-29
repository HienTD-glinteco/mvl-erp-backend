"""Import handler for ContractAppendix model."""

import logging

from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import Contract, ContractAppendix, Employee
from libs.drf.serializers import (
    FlexibleDateField,
    normalize_value,
)
from libs.strings import normalize_header

logger = logging.getLogger(__name__)

# Column mapping for import template (Vietnamese headers to field names)
COLUMN_MAPPING = {
    "số thứ tự": "row_number",
    "mã nhân viên": "employee_code",
    "số hợp đồng": "contract_number",
    "số phụ lục": "code",
    "ngày ký": "sign_date",
    "ngày hiệu lực": "effective_date",
    "nội dung thay đổi": "content",
    "ghi chú": "note",
}


class ContractAppendixImportSerializer(serializers.Serializer):
    """Serializer for contract appendix import row data.

    Uses FlexibleFields from libs.drf.serializers for flexible input parsing.
    """

    # Required fields
    sign_date = FlexibleDateField()
    effective_date = FlexibleDateField()

    # Optional fields
    content = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        """Validate date logic."""
        sign_date = attrs.get("sign_date")
        effective_date = attrs.get("effective_date")

        if sign_date and effective_date and sign_date > effective_date:
            raise serializers.ValidationError({"sign_date": _("Sign date must be on or before effective date")})

        return attrs


def pre_import_initialize(import_job_id: str, options: dict) -> None:
    """Pre-import initialization callback.

    Called once at the start of the import process before processing any rows.
    Prefetches all employees and contracts to avoid N+1 queries.

    Args:
        import_job_id: UUID of the import job
        options: Import options dictionary
    """
    # Prefetch all employees by code (case-insensitive)
    employees_by_code = {}
    for emp in Employee.objects.all():
        employees_by_code[emp.code.lower()] = emp
    options["_employees_by_code"] = employees_by_code

    # Prefetch all contracts by contract_number (code)
    # Key format: (employee_code, contract_code) for precise lookup
    contracts_by_key = {}
    for contract in Contract.objects.select_related("employee").all():
        if contract.code:
            # Store by contract code (case-insensitive)
            contracts_by_key[contract.code.lower()] = contract
            # Also store by (employee_code, contract_code) for cross-validation
            employee_code = contract.employee.code.lower() if contract.employee else ""
            contracts_by_key[(employee_code, contract.code.lower())] = contract
    options["_contracts_by_key"] = contracts_by_key

    # Prefetch existing appendices by code for duplicate checking
    appendices_by_code = {}
    for appendix in ContractAppendix.objects.all():
        if appendix.code:
            appendices_by_code[appendix.code.lower()] = appendix
    options["_appendices_by_code"] = appendices_by_code

    logger.info(
        "Import job %s: Prefetched %d employees, %d contracts, %d appendices",
        import_job_id,
        len(employees_by_code),
        len([k for k in contracts_by_key.keys() if isinstance(k, str)]),
        len(appendices_by_code),
    )


def _parse_row_to_dict(row: list, headers: list) -> dict:
    """Parse row list to dictionary using column mapping.

    Args:
        row: List of cell values from the row
        headers: List of header names

    Returns:
        Dictionary with field names as keys and cell values
    """
    row_dict = {}
    for i, header in enumerate(headers):
        if i < len(row):
            normalized_header = normalize_header(header)
            field_name = COLUMN_MAPPING.get(normalized_header, normalized_header)
            row_dict[field_name] = row[i]
    return row_dict


def _lookup_contract(contract_number: str, employee_code: str, options: dict) -> tuple[Contract | None, str | None]:
    """Lookup contract from prefetched data.

    Args:
        contract_number: Contract number/code to find
        employee_code: Employee code for cross-validation (optional)
        options: Import options with prefetched data

    Returns:
        Tuple of (Contract or None, error message or None)
    """
    contracts_by_key = options.get("_contracts_by_key", {})

    # Try to find contract by (employee_code, contract_code) if employee_code provided
    contract = None
    if employee_code:
        contract = contracts_by_key.get((employee_code.lower(), contract_number.lower()))

    # Fall back to lookup by contract code alone
    if not contract:
        contract = contracts_by_key.get(contract_number.lower())

    if not contract:
        return None, "Contract with number '%s' not found" % contract_number

    return contract, None


def _validate_employee_contract_match(
    employee_code: str, contract: Contract, contract_number: str, options: dict
) -> str | None:
    """Cross-validate that employee matches the contract.

    Args:
        employee_code: Employee code to validate
        contract: Contract to validate against
        contract_number: Contract number for error message
        options: Import options with prefetched data

    Returns:
        Error message if validation fails, None if valid
    """
    if not employee_code:
        return None

    employees_by_code = options.get("_employees_by_code", {})
    employee = employees_by_code.get(employee_code.lower())

    if not employee:
        return "Employee with code '%s' not found" % employee_code

    if contract.employee != employee:
        return "Contract '%s' does not belong to employee '%s'" % (contract_number, employee_code)

    return None


def _validate_serializer_data(row_dict: dict) -> tuple[dict | None, str | None]:
    """Validate import data using serializer.

    Args:
        row_dict: Dictionary of parsed row data

    Returns:
        Tuple of (validated data or None, error message or None)
    """
    serializer_data = {
        "sign_date": row_dict.get("sign_date"),
        "effective_date": row_dict.get("effective_date"),
        "content": normalize_value(row_dict.get("content", "")),
        "note": normalize_value(row_dict.get("note", "")),
    }

    serializer = ContractAppendixImportSerializer(data=serializer_data)
    if not serializer.is_valid():
        # Format validation errors
        error_messages = []
        for field, errors in serializer.errors.items():
            if isinstance(errors, list):
                error_messages.extend([str(e) for e in errors])
            else:
                error_messages.append(str(errors))
        return None, "; ".join(error_messages)

    return serializer.validated_data, None


def _check_existing_appendix(
    appendix_code: str, allow_update: bool, options: dict
) -> tuple[ContractAppendix | None, bool, str | None]:
    """Check for existing appendix and determine if should skip.

    Args:
        appendix_code: Appendix code to check
        allow_update: Whether updates are allowed
        options: Import options with prefetched data

    Returns:
        Tuple of (existing appendix or None, should_skip flag, skip message or None)
    """
    if not appendix_code:
        return None, False, None

    appendices_by_code = options.get("_appendices_by_code", {})
    existing_appendix = appendices_by_code.get(appendix_code.lower())

    if existing_appendix and not allow_update:
        return (
            existing_appendix,
            True,
            "Appendix with code '%s' already exists (allow_update=False)" % appendix_code,
        )

    return existing_appendix, False, None


def _update_existing_appendix(existing_appendix: ContractAppendix, appendix_data: dict, contract: Contract) -> dict:
    """Update an existing appendix record.

    Args:
        existing_appendix: Existing appendix to update
        appendix_data: New data to update with
        contract: Associated contract

    Returns:
        Success result dictionary
    """
    for key, value in appendix_data.items():
        if key != "contract":  # Don't update contract
            setattr(existing_appendix, key, value)
    existing_appendix.save()
    logger.info("Updated appendix %s for contract %s", existing_appendix.code, contract.code)

    return {
        "appendix_id": str(existing_appendix.id),
        "appendix_code": existing_appendix.code,
        "contract_code": contract.code,
    }


def _create_new_appendix(appendix_data: dict, appendix_code: str, contract: Contract, options: dict) -> dict:
    """Create a new appendix record.

    Args:
        appendix_data: Data for new appendix
        appendix_code: Explicit code (if provided)
        contract: Associated contract
        options: Import options with appendices cache

    Returns:
        Result dictionary with new appendix info
    """
    # If code is provided in import, set it; otherwise let signal auto-generate
    if appendix_code:
        appendix_data["code"] = appendix_code

    appendix = ContractAppendix.objects.create(**appendix_data)
    logger.info("Created appendix %s for contract %s", appendix.code, contract.code)

    # Update cache with new appendix
    appendices_by_code = options.get("_appendices_by_code", {})
    if appendix.code:
        appendices_by_code[appendix.code.lower()] = appendix

    return {
        "appendix_id": str(appendix.id),
        "appendix_code": appendix.code,
        "contract_code": contract.code,
    }


def import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:
    """Import handler for contract appendices.

    Processes a single row from the import file and creates a ContractAppendix.
    Uses ContractAppendixImportSerializer with FlexibleFields for validation.

    Args:
        row_index: 1-based row index (excluding header)
        row: List of cell values from the row
        import_job_id: UUID string of the ImportJob record
        options: Import options dictionary

    Returns:
        dict: Result with format:
            Success: {"ok": True, "result": {...}, "action": "created"|"updated"|"skipped"}
            Failure: {"ok": False, "error": "..."}
    """
    try:
        # Get headers from options
        headers = options.get("headers", [])
        if not headers:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Headers not provided in options",
                "action": "skipped",
            }

        # Parse row to dictionary
        row_dict = _parse_row_to_dict(row, headers)

        # Check for missing required fields early (skip gracefully)
        employee_code = normalize_value(row_dict.get("employee_code", ""))
        contract_number = normalize_value(row_dict.get("contract_number", ""))

        if not contract_number:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "warnings": ["Missing required field: contract number"],
            }

        # Lookup contract
        contract, contract_error = _lookup_contract(contract_number, employee_code, options)
        if contract_error:
            return {
                "ok": False,
                "row_index": row_index,
                "error": contract_error,
                "action": "skipped",
            }

        # Cross-validate employee code if provided
        employee_error = _validate_employee_contract_match(employee_code, contract, contract_number, options)
        if employee_error:
            return {
                "ok": False,
                "row_index": row_index,
                "error": employee_error,
                "action": "skipped",
            }

        # Validate using serializer
        validated_data, validation_error = _validate_serializer_data(row_dict)
        if validation_error:
            return {
                "ok": False,
                "row_index": row_index,
                "error": validation_error,
                "action": "skipped",
            }

        # Get appendix code from import (if provided)
        appendix_code = normalize_value(row_dict.get("code", ""))

        # Check for existing appendix and handle allow_update
        allow_update = options.get("allow_update", False)
        existing_appendix, should_skip, skip_message = _check_existing_appendix(appendix_code, allow_update, options)

        if should_skip:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "appendix_code": existing_appendix.code if existing_appendix else None,
                "warnings": [skip_message] if skip_message else [],
            }

        # Build appendix data
        appendix_data = {
            "contract": contract,
            "sign_date": validated_data["sign_date"],
            "effective_date": validated_data["effective_date"],
            "content": validated_data.get("content", ""),
            "note": validated_data.get("note", ""),
        }

        # Create or update appendix
        with transaction.atomic():
            if existing_appendix and allow_update:
                result = _update_existing_appendix(existing_appendix, appendix_data, contract)
                return {
                    "ok": True,
                    "row_index": row_index,
                    "action": "updated",
                    "appendix_code": existing_appendix.code,
                    "warnings": [],
                    "result": result,
                }

            result = _create_new_appendix(appendix_data, appendix_code, contract, options)
            return {
                "ok": True,
                "row_index": row_index,
                "action": "created",
                "appendix_code": result["appendix_code"],
                "warnings": [],
                "result": result,
            }

    except Exception as e:
        logger.exception("Import handler error at row %d: %s", row_index, e)
        return {
            "ok": False,
            "row_index": row_index,
            "error": str(e),
            "action": "skipped",
        }
