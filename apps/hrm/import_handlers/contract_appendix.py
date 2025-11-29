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


def normalize_header(header: str) -> str:
    """Normalize header name by stripping and lowercasing."""
    if not header:
        return ""
    return str(header).strip().lower()


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


def import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:  # noqa: C901
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

        # Map row to dictionary using column mapping
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(row):
                normalized_header = normalize_header(header)
                field_name = COLUMN_MAPPING.get(normalized_header, normalized_header)
                row_dict[field_name] = row[i]

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

        # Lookup contract from prefetched data
        contracts_by_key = options.get("_contracts_by_key", {})

        # Try to find contract by (employee_code, contract_code) if employee_code provided
        contract = None
        if employee_code:
            contract = contracts_by_key.get((employee_code.lower(), contract_number.lower()))

        # Fall back to lookup by contract code alone
        if not contract:
            contract = contracts_by_key.get(contract_number.lower())

        if not contract:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Contract with number '%s' not found" % contract_number,
                "action": "skipped",
            }

        # Cross-validate employee code if provided
        if employee_code:
            employees_by_code = options.get("_employees_by_code", {})
            employee = employees_by_code.get(employee_code.lower())
            if not employee:
                return {
                    "ok": False,
                    "row_index": row_index,
                    "error": "Employee with code '%s' not found" % employee_code,
                    "action": "skipped",
                }
            if contract.employee != employee:
                return {
                    "ok": False,
                    "row_index": row_index,
                    "error": "Contract '%s' does not belong to employee '%s'" % (contract_number, employee_code),
                    "action": "skipped",
                }

        # Prepare serializer data - FlexibleFields handle parsing
        serializer_data = {
            "sign_date": row_dict.get("sign_date"),
            "effective_date": row_dict.get("effective_date"),
            "content": normalize_value(row_dict.get("content", "")),
            "note": normalize_value(row_dict.get("note", "")),
        }

        # Validate using serializer
        serializer = ContractAppendixImportSerializer(data=serializer_data)
        if not serializer.is_valid():
            # Format validation errors
            error_messages = []
            for field, errors in serializer.errors.items():
                if isinstance(errors, list):
                    error_messages.extend([str(e) for e in errors])
                else:
                    error_messages.append(str(errors))

            return {
                "ok": False,
                "row_index": row_index,
                "error": "; ".join(error_messages),
                "action": "skipped",
            }

        validated_data = serializer.validated_data

        # Get appendix code from import (if provided)
        appendix_code = normalize_value(row_dict.get("code", ""))

        # Check for existing appendix and handle allow_update
        allow_update = options.get("allow_update", False)
        appendices_by_code = options.get("_appendices_by_code", {})
        existing_appendix = None

        if appendix_code:
            existing_appendix = appendices_by_code.get(appendix_code.lower())

        if existing_appendix and not allow_update:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "appendix_code": existing_appendix.code,
                "warnings": ["Appendix with code '%s' already exists (allow_update=False)" % appendix_code],
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
            # Handle update case with early return
            if existing_appendix and allow_update:
                for key, value in appendix_data.items():
                    if key != "contract":  # Don't update contract
                        setattr(existing_appendix, key, value)
                existing_appendix.save()
                logger.info("Updated appendix %s for contract %s", existing_appendix.code, contract.code)

                return {
                    "ok": True,
                    "row_index": row_index,
                    "action": "updated",
                    "appendix_code": existing_appendix.code,
                    "warnings": [],
                    "result": {
                        "appendix_id": str(existing_appendix.id),
                        "appendix_code": existing_appendix.code,
                        "contract_code": contract.code,
                    },
                }

            # Create new appendix
            # If code is provided in import, set it; otherwise let signal auto-generate
            if appendix_code:
                appendix_data["code"] = appendix_code

            appendix = ContractAppendix.objects.create(**appendix_data)
            logger.info("Created appendix %s for contract %s", appendix.code, contract.code)

            # Update cache with new appendix
            if appendix.code:
                appendices_by_code[appendix.code.lower()] = appendix

            return {
                "ok": True,
                "row_index": row_index,
                "action": "created",
                "appendix_code": appendix.code,
                "warnings": [],
                "result": {
                    "appendix_id": str(appendix.id),
                    "appendix_code": appendix.code,
                    "contract_code": contract.code,
                },
            }

    except Exception as e:
        logger.exception("Import handler error at row %d: %s", row_index, e)
        return {
            "ok": False,
            "row_index": row_index,
            "error": str(e),
            "action": "skipped",
        }
