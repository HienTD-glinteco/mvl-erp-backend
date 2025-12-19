"""Import handler for Contract updates."""

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

# Column mapping for import template (same as creation/appendix mostly)
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
    "nội dung": "content",
    "ghi chú": "note",
}

# Tax calculation method mapping
TAX_CALCULATION_MAPPING = {
    "lũy tiến": ContractType.TaxCalculationMethod.PROGRESSIVE,
    "progressive": ContractType.TaxCalculationMethod.PROGRESSIVE,
    "10%": ContractType.TaxCalculationMethod.FLAT_10,
    "flat_10": ContractType.TaxCalculationMethod.FLAT_10,
    "không": ContractType.TaxCalculationMethod.NONE,
    "none": ContractType.TaxCalculationMethod.NONE,
}

# Net percentage mapping
NET_PERCENTAGE_MAPPING = {
    "100": ContractType.NetPercentage.FULL,
    "100%": ContractType.NetPercentage.FULL,
    "85": ContractType.NetPercentage.REDUCED,
    "85%": ContractType.NetPercentage.REDUCED,
}


class ContractUpdateImportSerializer(serializers.Serializer):
    """Serializer for contract update import row data."""

    # Required fields to identify contract (combined with employee/contract_type lookup)
    effective_date = FlexibleDateField(required=True)

    # Optional fields to update
    sign_date = FlexibleDateField(required=False, allow_null=True)
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
    working_conditions = serializers.CharField(required=False, allow_blank=True)
    rights_and_obligations = serializers.CharField(required=False, allow_blank=True)
    terms = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        """Validate date logic."""
        sign_date = attrs.get("sign_date")
        effective_date = attrs.get("effective_date")
        expiration_date = attrs.get("expiration_date")

        # Note: In update, we might not have all dates, so checks are conditional
        # But generally we trust the user knows what they are doing, or we check against existing values if we fetch them here.
        # For simplicity, we just check if both are present in the update payload.

        if sign_date and effective_date and sign_date > effective_date:
            raise serializers.ValidationError({"sign_date": _("Sign date must be on or before effective date")})

        if effective_date and expiration_date and effective_date > expiration_date:
            raise serializers.ValidationError(
                {"expiration_date": _("Expiration date must be on or after effective date")}
            )

        return attrs


def pre_import_initialize(import_job_id: str, options: dict) -> None:
    """Pre-import initialization callback."""
    # Prefetch all employees
    employees_by_code = {}
    for emp in Employee.objects.all():
        employees_by_code[emp.code.lower()] = emp
    options["_employees_by_code"] = employees_by_code

    # Prefetch all contract types
    contract_types_by_code = {}
    for ct in ContractType.objects.all():
        contract_code = ct.code or ""
        contract_types_by_code[contract_code.lower()] = ct
    options["_contract_types_by_code"] = contract_types_by_code


def import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:  # noqa: C901
    """Import handler for updating existing contracts."""
    try:
        headers = options.get("headers", [])
        if not headers:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Headers not provided in options",
                "action": "skipped",
            }

        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(row):
                normalized_header = normalize_header(header)
                field_name = COLUMN_MAPPING.get(normalized_header, normalized_header)
                row_dict[field_name] = row[i]

        employee_code = normalize_value(row_dict.get("employee_code", ""))
        contract_type_code = normalize_value(row_dict.get("contract_type_code", ""))
        contract_number = normalize_value(row_dict.get("contract_number", ""))

        # Identify Contract
        # Strategy:
        # 1. By Contract Number (if provided)
        # 2. By Employee + Contract Type + Effective Date

        existing_contract = None

        if contract_number:
            existing_contract = Contract.objects.filter(contract_number=contract_number).first()

        # If not found by number, try finding by E + CT + EffectiveDate
        if not existing_contract:
            if not employee_code or not contract_type_code:
                 return {
                    "ok": True, # Skipped technically
                    "row_index": row_index,
                    "action": "skipped",
                    "warnings": ["Cannot identify contract: missing contract number or employee/type code"],
                }

            employees_by_code = options.get("_employees_by_code", {})
            employee = employees_by_code.get(str(employee_code).lower())
            if not employee:
                employee = Employee.objects.filter(code=employee_code).first()

            contract_types_by_code = options.get("_contract_types_by_code", {})
            contract_type = contract_types_by_code.get(str(contract_type_code).lower())
            if not contract_type:
                contract_type = ContractType.objects.filter(code=contract_type_code).first()

            # For date, we need to parse it using serializer first to match format
            # We'll do a mini-validation/parsing here just for the date
            serializer_data_raw = {
                "effective_date": row_dict.get("effective_date"),
            }
            # Use serializer just to parse date
            date_serializer = ContractUpdateImportSerializer(data=serializer_data_raw, partial=True)
            if not date_serializer.is_valid():
                 return {
                    "ok": False,
                    "row_index": row_index,
                    "error": "Invalid effective date format",
                    "action": "skipped",
                }
            effective_date = date_serializer.validated_data.get("effective_date")

            if employee and contract_type and effective_date:
                existing_contract = Contract.objects.filter(
                    employee=employee,
                    contract_type=contract_type,
                    effective_date=effective_date
                ).first()

        if not existing_contract:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Contract not found",
                "action": "skipped",
            }

        # Check Category
        if existing_contract.contract_type.category != ContractType.Category.CONTRACT:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Found contract is not a standard contract (it is an appendix)",
                "action": "skipped",
            }

        # Check Status
        if existing_contract.status != Contract.ContractStatus.DRAFT:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Only DRAFT contracts can be updated. Current status: %s" % existing_contract.status,
                "action": "skipped",
            }

        # Prepare full data for update
        serializer_data = {
            "contract_number": contract_number,
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
            "content": normalize_value(row_dict.get("content", "")),
            "note": normalize_value(row_dict.get("note", "")),
        }

        # Clean empty keys
        serializer_data = {k: v for k, v in serializer_data.items() if v is not None and v != ""}

        serializer = ContractUpdateImportSerializer(data=serializer_data, partial=True)
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

        with transaction.atomic():
            for key, value in validated_data.items():
                setattr(existing_contract, key, value)
            existing_contract.save()

            logger.info("Updated contract %s", existing_contract.code)

            return {
                "ok": True,
                "row_index": row_index,
                "action": "updated",
                "contract_code": existing_contract.code,
                "warnings": [],
                "result": {
                    "contract_id": str(existing_contract.id),
                    "contract_code": existing_contract.code,
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
