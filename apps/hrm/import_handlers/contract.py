"""Import handler for Contract model."""

import logging

from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import Contract, ContractType, Employee
from libs.drf.serializers import (
    FlexibleBooleanField,
    FlexibleChoiceField,
    FlexibleDateField,
    FlexibleDecimalField,
    normalize_value,
)
from libs.strings import normalize_header

logger = logging.getLogger(__name__)

# Column mapping for import template (Vietnamese headers to field names)
COLUMN_MAPPING = {
    "số thứ tự": "row_number",
    "mã nhân viên": "employee_code",
    "mã loại hợp đồng": "contract_type_code",
    "số hợp đồng": "contract_number",
    "ngày ký": "sign_date",
    "ngày hiệu lực": "effective_date",
    "ngày hết hạn": "expiration_date",
    "lương cơ bản": "base_salary",
    "lương kpi": "kpi_salary",
    "phụ cấp ăn trưa": "lunch_allowance",
    "phụ cấp điện thoại": "phone_allowance",
    "phụ cấp khác": "other_allowance",
    "tỷ lệ lương net": "net_percentage",
    "phương pháp tính thuế": "tax_calculation_method",
    "có bảo hiểm xã hội": "has_social_insurance",
    "điều kiện làm việc": "working_conditions",
    "quyền và nghĩa vụ": "rights_and_obligations",
    "điều khoản": "terms",
    "ghi chú": "note",
}

# Status is always DRAFT for imported contracts
DEFAULT_STATUS = Contract.ContractStatus.DRAFT

# Tax calculation method mapping for FlexibleChoiceField
TAX_CALCULATION_MAPPING = {
    "lũy tiến": ContractType.TaxCalculationMethod.PROGRESSIVE,
    "progressive": ContractType.TaxCalculationMethod.PROGRESSIVE,
    "10%": ContractType.TaxCalculationMethod.FLAT_10,
    "flat_10": ContractType.TaxCalculationMethod.FLAT_10,
    "không": ContractType.TaxCalculationMethod.NONE,
    "none": ContractType.TaxCalculationMethod.NONE,
}

# Net percentage mapping for FlexibleChoiceField
NET_PERCENTAGE_MAPPING = {
    "100": ContractType.NetPercentage.FULL,
    "100%": ContractType.NetPercentage.FULL,
    "85": ContractType.NetPercentage.REDUCED,
    "85%": ContractType.NetPercentage.REDUCED,
}


class ContractImportSerializer(serializers.Serializer):
    """Serializer for contract import row data.

    Uses FlexibleFields from libs.drf.serializers for flexible input parsing.
    """

    # Required fields
    sign_date = FlexibleDateField()
    effective_date = FlexibleDateField()

    # Optional fields
    contract_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    expiration_date = FlexibleDateField(required=False, allow_null=True)
    base_salary = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    kpi_salary = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    lunch_allowance = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    phone_allowance = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    other_allowance = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    net_percentage = FlexibleChoiceField(
        choices=ContractType.NetPercentage.choices,
        value_mapping=NET_PERCENTAGE_MAPPING,
        required=False,
        allow_null=True,
    )
    tax_calculation_method = FlexibleChoiceField(
        choices=ContractType.TaxCalculationMethod.choices,
        value_mapping=TAX_CALCULATION_MAPPING,
        required=False,
        allow_null=True,
    )
    has_social_insurance = FlexibleBooleanField(required=False, allow_null=True)
    working_conditions = serializers.CharField(required=False, allow_blank=True, default="")
    rights_and_obligations = serializers.CharField(required=False, allow_blank=True, default="")
    terms = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        """Validate date logic."""
        sign_date = attrs.get("sign_date")
        effective_date = attrs.get("effective_date")
        expiration_date = attrs.get("expiration_date")

        if sign_date and effective_date and sign_date > effective_date:
            raise serializers.ValidationError({"sign_date": _("Sign date must be on or before effective date")})

        if effective_date and expiration_date and effective_date > expiration_date:
            raise serializers.ValidationError(
                {"expiration_date": _("Expiration date must be on or after effective date")}
            )

        return attrs


def copy_snapshot_from_contract_type(contract_type: ContractType, contract_data: dict) -> None:
    """Copy snapshot data from ContractType to contract data.

    Only copies fields that are not already provided in contract_data.

    Args:
        contract_type: ContractType instance
        contract_data: Contract data dict to update
    """
    snapshot_fields = [
        "base_salary",
        "lunch_allowance",
        "phone_allowance",
        "other_allowance",
        "net_percentage",
        "tax_calculation_method",
        "has_social_insurance",
        "working_conditions",
        "rights_and_obligations",
        "terms",
    ]

    for field in snapshot_fields:
        if field not in contract_data or contract_data[field] is None:
            contract_data[field] = getattr(contract_type, field)


def pre_import_initialize(import_job_id: str, options: dict) -> None:
    """Pre-import initialization callback.

    Called once at the start of the import process before processing any rows.
    Prefetches all employees and contract types to avoid N+1 queries.

    Args:
        import_job_id: UUID of the import job
        options: Import options dictionary
    """
    # Prefetch all employees by code (case-insensitive)
    employees_by_code = {}
    for emp in Employee.objects.all():
        employees_by_code[emp.code.lower()] = emp
    options["_employees_by_code"] = employees_by_code

    # Prefetch all contract types by code (case-insensitive)
    contract_types_by_code = {}
    for ct in ContractType.objects.all():
        contract_code = ct.code or ""
        contract_types_by_code[contract_code.lower()] = ct
    options["_contract_types_by_code"] = contract_types_by_code

    logger.info(
        "Import job %s: Prefetched %d employees and %d contract types",
        import_job_id,
        len(employees_by_code),
        len(contract_types_by_code),
    )


def import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:  # noqa: C901
    """Import handler for contracts.

    Processes a single row from the import file and creates a Contract.
    Uses ContractImportSerializer with FlexibleFields for validation.

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
        contract_type_code = normalize_value(row_dict.get("contract_type_code", ""))

        if not employee_code:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "warnings": ["Missing required field: employee code"],
            }

        if not contract_type_code:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "warnings": ["Missing required field: contract type code"],
            }

        # Lookup employee from prefetched data
        employees_by_code = options.get("_employees_by_code", {})
        employee = employees_by_code.get(str(employee_code).lower())
        if not employee:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Employee with code '%s' not found" % employee_code,
                "action": "skipped",
            }

        # Lookup contract type from prefetched data
        contract_types_by_code = options.get("_contract_types_by_code", {})
        contract_type = contract_types_by_code.get(str(contract_type_code).lower())
        if not contract_type:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Contract type with code '%s' not found" % contract_type_code,
                "action": "skipped",
            }

        # Prepare serializer data - FlexibleFields handle parsing
        serializer_data = {
            "contract_number": normalize_value(row_dict.get("contract_number", "")),
            "sign_date": row_dict.get("sign_date"),
            "effective_date": row_dict.get("effective_date"),
            "expiration_date": row_dict.get("expiration_date"),
            "base_salary": row_dict.get("base_salary"),
            "kpi_salary": row_dict.get("kpi_salary"),
            "lunch_allowance": row_dict.get("lunch_allowance"),
            "phone_allowance": row_dict.get("phone_allowance"),
            "other_allowance": row_dict.get("other_allowance"),
            "net_percentage": row_dict.get("net_percentage"),
            "tax_calculation_method": row_dict.get("tax_calculation_method"),
            "has_social_insurance": row_dict.get("has_social_insurance"),
            "working_conditions": normalize_value(row_dict.get("working_conditions", "")),
            "rights_and_obligations": normalize_value(row_dict.get("rights_and_obligations", "")),
            "terms": normalize_value(row_dict.get("terms", "")),
            "note": normalize_value(row_dict.get("note", "")),
        }

        # Validate using serializer
        serializer = ContractImportSerializer(data=serializer_data)
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

        # Build contract data
        contract_data = {
            "employee": employee,
            "contract_type": contract_type,
            "sign_date": validated_data["sign_date"],
            "effective_date": validated_data["effective_date"],
            "expiration_date": validated_data.get("expiration_date"),
            "status": DEFAULT_STATUS,
        }

        # Add optional fields if provided
        optional_fields = [
            "contract_number",
            "base_salary",
            "kpi_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
            "net_percentage",
            "tax_calculation_method",
            "has_social_insurance",
            "working_conditions",
            "rights_and_obligations",
            "terms",
            "note",
        ]

        for field in optional_fields:
            value = validated_data.get(field)
            if value is not None and value != "":
                contract_data[field] = value

        # Copy snapshot data from contract type for fields not explicitly provided
        copy_snapshot_from_contract_type(contract_type, contract_data)

        # Check for existing contract and handle allow_update
        allow_update = options.get("allow_update", False)
        existing_contract = Contract.objects.filter(
            employee=employee,
            effective_date=validated_data["effective_date"],
            contract_type=contract_type,
        ).first()

        if existing_contract and not allow_update:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "contract_code": existing_contract.code,
                "warnings": [
                    "Contract for employee '%s' with same effective date and contract type already exists (allow_update=False)"
                    % employee_code
                ],
            }

        # Create or update contract
        with transaction.atomic():
            # Handle update case with early return
            if existing_contract and allow_update:
                if existing_contract.status != Contract.ContractStatus.DRAFT:
                    return {
                        "ok": False,
                        "row_index": row_index,
                        "error": "Cannot update contract %s: only DRAFT contracts can be updated"
                        % existing_contract.code,
                        "action": "skipped",
                    }

                for key, value in contract_data.items():
                    if key not in ["employee", "contract_type"]:
                        setattr(existing_contract, key, value)
                existing_contract.save()
                logger.info("Updated contract %s for employee %s", existing_contract.code, employee.code)

                return {
                    "ok": True,
                    "row_index": row_index,
                    "action": "updated",
                    "contract_code": existing_contract.code,
                    "warnings": [],
                    "result": {
                        "contract_id": str(existing_contract.id),
                        "contract_code": existing_contract.code,
                        "employee_code": employee.code,
                    },
                }

            # Create new contract
            contract = Contract.objects.create(**contract_data)
            logger.info("Created contract %s for employee %s", contract.code, employee.code)

            return {
                "ok": True,
                "row_index": row_index,
                "action": "created",
                "contract_code": contract.code,
                "warnings": [],
                "result": {
                    "contract_id": str(contract.id),
                    "contract_code": contract.code,
                    "employee_code": employee.code,
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
