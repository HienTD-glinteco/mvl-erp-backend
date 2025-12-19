"""Import handler for Contract Appendix."""

import logging

from django.db import transaction
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

# Column mapping for import template (based on contract_appendix_template.xlsx)
COLUMN_MAPPING = {
    "số thứ tự": "row_number",
    "mã nhân viên": "employee_code",
    "số hợp đồng": "parent_contract_number",
    "số phụ lục": "contract_number",
    "ngày ký": "sign_date",
    "ngày hiệu lực": "effective_date",
    "lương cơ bản": "base_salary",
    "lương kpi": "kpi_salary",
    "phụ cấp ăn trưa": "lunch_allowance",
    "phụ cấp điện thoại": "phone_allowance",
    "phụ cấp khác": "other_allowance",
    "nội dung thay đổi": "content",
    "ghi chú": "note",
}

# Status is always DRAFT for imported contracts/appendices
DEFAULT_STATUS = Contract.ContractStatus.DRAFT


class ContractAppendixImportSerializer(serializers.Serializer):
    """Serializer for contract appendix import row data."""

    # Required fields
    sign_date = FlexibleDateField()
    effective_date = FlexibleDateField()
    parent_contract_number = serializers.CharField(required=True, allow_blank=False)

    # Optional fields
    contract_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    base_salary = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    kpi_salary = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    lunch_allowance = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    phone_allowance = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    other_allowance = FlexibleDecimalField(max_digits=20, decimal_places=0, required=False, allow_null=True)
    content = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        """Validate date logic."""
        sign_date = attrs.get("sign_date")
        effective_date = attrs.get("effective_date")

        if sign_date and effective_date and sign_date > effective_date:
            raise serializers.ValidationError({"sign_date": "Sign date must be on or before effective date"})

        return attrs


def copy_snapshot_from_contract_type(contract_type: ContractType, contract_data: dict) -> None:
    """Copy snapshot data from ContractType to contract data."""
    snapshot_fields = [
        "base_salary",
        "lunch_allowance",
        "phone_allowance",
        "other_allowance",
        # Default others that are not in template
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
    """Pre-import initialization callback."""
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

    # Get Appendix Contract Type (Assuming one generic type for appendices based on logic or need to fetch default)
    # The requirement says: "Lookup contract type". But the template DOES NOT have contract_type column.
    # We must infer or use a default Appendix Contract Type.
    # Generally, there should be a system default or we pick the first one with category='appendix'.
    appendix_type = ContractType.objects.filter(category=ContractType.Category.APPENDIX).first()
    if appendix_type:
        options["_appendix_contract_type"] = appendix_type
    else:
        logger.warning("No ContractType with category='appendix' found.")


def import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:  # noqa: C901
    """Import handler for contract appendices."""
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

        # Check for missing required fields early
        employee_code = normalize_value(row_dict.get("employee_code", ""))

        # NOTE: Template doesn't have contract_type. We use default appendix type.
        contract_type = options.get("_appendix_contract_type")

        if not employee_code:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "warnings": ["Missing required field: employee code"],
            }

        if not contract_type:
             return {
                "ok": False,
                "row_index": row_index,
                "error": "System configuration error: No default 'Appendix' Contract Type found.",
                "action": "skipped",
            }

        if contract_type.category != ContractType.Category.APPENDIX:
             return {
                "ok": False,
                "row_index": row_index,
                "error": "Invalid contract type category. Expected 'appendix', got '%s'" % contract_type.category,
                "action": "skipped",
            }

        # Lookup employee
        employees_by_code = options.get("_employees_by_code", {})
        employee = employees_by_code.get(str(employee_code).lower())
        if not employee:
            employee = Employee.objects.filter(code=employee_code).first()
            if not employee:
                return {
                    "ok": False,
                    "row_index": row_index,
                    "error": "Employee with code '%s' not found" % employee_code,
                    "action": "skipped",
                }

        # Handle parent contract for appendices
        parent_contract_number = normalize_value(row_dict.get("parent_contract_number", ""))
        if not parent_contract_number:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Parent contract number is required for appendices",
                "action": "skipped",
            }

        parent_contract = Contract.objects.filter(contract_number=parent_contract_number).first()
        if not parent_contract:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Parent contract with number '%s' not found" % parent_contract_number,
                "action": "skipped",
            }

        # Verify parent contract belongs to the same employee
        if parent_contract.employee_id != employee.id:
             return {
                "ok": False,
                "row_index": row_index,
                "error": "Parent contract %s belongs to a different employee" % parent_contract_number,
                "action": "skipped",
            }

        # Prepare serializer data
        serializer_data = {
            "contract_number": normalize_value(row_dict.get("contract_number", "")),
            "sign_date": row_dict.get("sign_date"),
            "effective_date": row_dict.get("effective_date"),
            "base_salary": row_dict.get("base_salary"),
            "kpi_salary": row_dict.get("kpi_salary"),
            "lunch_allowance": row_dict.get("lunch_allowance"),
            "phone_allowance": row_dict.get("phone_allowance"),
            "other_allowance": row_dict.get("other_allowance"),
            "content": normalize_value(row_dict.get("content", "")),
            "note": normalize_value(row_dict.get("note", "")),
            "parent_contract_number": parent_contract_number,
        }

        # Validate using serializer
        serializer = ContractAppendixImportSerializer(data=serializer_data)
        if not serializer.is_valid():
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
            "status": DEFAULT_STATUS,
            "parent_contract": parent_contract,
        }

        # Add optional fields if provided
        optional_fields = [
            "contract_number",
            "base_salary",
            "kpi_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
            "content",
            "note",
        ]

        for field in optional_fields:
            value = validated_data.get(field)
            if value is not None and value != "":
                contract_data[field] = value

        # Copy snapshot data from contract type
        copy_snapshot_from_contract_type(contract_type, contract_data)

        # Check for existing appendix (by number)
        contract_number = validated_data.get("contract_number")
        existing_contract = None
        if contract_number:
            existing_contract = Contract.objects.filter(contract_number=contract_number).first()

        # Create or update
        with transaction.atomic():
            if existing_contract:
                # Basic update for appendix if exists and number matches
                if existing_contract.status != Contract.ContractStatus.DRAFT:
                     return {
                        "ok": False,
                        "row_index": row_index,
                        "error": "Cannot update appendix %s: only DRAFT appendices can be updated"
                        % existing_contract.code,
                        "action": "skipped",
                    }

                for key, value in contract_data.items():
                    if key not in ["employee", "contract_type", "parent_contract"]:
                         setattr(existing_contract, key, value)
                existing_contract.save()

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

            # Create new appendix
            contract = Contract.objects.create(**contract_data)
            logger.info("Created appendix %s for employee %s", contract.code, employee.code)

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
