"""Import handler for Contract model."""

import logging
from datetime import date, datetime
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import Contract, ContractType, Employee

logger = logging.getLogger(__name__)

# Column mapping for import template (Vietnamese headers to field names)
COLUMN_MAPPING = {
    "số thứ tự": "row_number",
    "mã nhân viên": "employee_code",
    "mã loại hợp đồng": "contract_type_code",
    "ngày ký": "sign_date",
    "ngày hiệu lực": "effective_date",
    "ngày hết hạn": "expiration_date",
    "lương cơ bản": "base_salary",
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

# Boolean mapping for has_social_insurance (Vietnamese support)
BOOLEAN_MAPPING = {
    "có": True,
    "yes": True,
    "true": True,
    "1": True,
    "không": False,
    "no": False,
    "false": False,
    "0": False,
}


class FlexibleDateField(serializers.DateField):
    """DateField that supports multiple date formats commonly used in imports."""

    def __init__(self, **kwargs):
        kwargs.setdefault("input_formats", [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
            "iso-8601",
        ])
        super().__init__(**kwargs)

    def to_internal_value(self, value):
        if not value or (isinstance(value, str) and value.strip() in ("", "-")):
            return None

        # Handle date/datetime objects directly
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        return super().to_internal_value(value)


class FlexibleDecimalField(serializers.DecimalField):
    """DecimalField that handles formatted numbers (e.g., with commas)."""

    def to_internal_value(self, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None

        # Clean up formatted numbers
        if isinstance(value, str):
            value = value.strip().replace(",", "").replace(" ", "")

        return super().to_internal_value(value)


class FlexibleBooleanField(serializers.BooleanField):
    """BooleanField that supports Vietnamese boolean values."""

    def to_internal_value(self, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.strip().lower()
            if value_lower in BOOLEAN_MAPPING:
                return BOOLEAN_MAPPING[value_lower]

        return super().to_internal_value(value)


class EmployeeCodeField(serializers.CharField):
    """Field that validates and converts employee code to Employee instance."""

    def to_internal_value(self, value):
        if not value or (isinstance(value, str) and value.strip() == ""):
            raise serializers.ValidationError(_("Employee code is required"))

        code = str(value).strip()
        employee = Employee.objects.filter(code__iexact=code).first()
        if not employee:
            raise serializers.ValidationError(_(f"Employee with code '{code}' not found"))

        return employee


class ContractTypeCodeField(serializers.CharField):
    """Field that validates and converts contract type code to ContractType instance."""

    def to_internal_value(self, value):
        if not value or (isinstance(value, str) and value.strip() == ""):
            raise serializers.ValidationError(_("Contract type code is required"))

        code = str(value).strip()
        contract_type = ContractType.objects.filter(code__iexact=code).first()
        if not contract_type:
            raise serializers.ValidationError(_(f"Contract type with code '{code}' not found"))

        return contract_type


class NetPercentageField(serializers.CharField):
    """Field that maps net percentage values to choices."""

    def to_internal_value(self, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None

        value_str = str(value).strip().lower()
        if value_str in NET_PERCENTAGE_MAPPING:
            return NET_PERCENTAGE_MAPPING[value_str]

        raise serializers.ValidationError(_(f"Unknown net percentage: {value}"))


class TaxCalculationMethodField(serializers.CharField):
    """Field that maps tax calculation method values to choices."""

    def to_internal_value(self, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None

        value_str = str(value).strip().lower()
        if value_str in TAX_CALCULATION_MAPPING:
            return TAX_CALCULATION_MAPPING[value_str]

        raise serializers.ValidationError(_(f"Unknown tax calculation method: {value}"))


class ContractImportSerializer(serializers.Serializer):
    """Serializer for contract import row data.

    Handles parsing, validation, and transformation of import row data.
    Uses custom fields for flexible parsing of dates, decimals, and lookups.
    """

    # Required fields
    employee_code = EmployeeCodeField()
    contract_type_code = ContractTypeCodeField()
    sign_date = FlexibleDateField()
    effective_date = FlexibleDateField()

    # Optional fields
    expiration_date = FlexibleDateField(required=False, allow_null=True)
    base_salary = FlexibleDecimalField(
        max_digits=20, decimal_places=0, required=False, allow_null=True
    )
    lunch_allowance = FlexibleDecimalField(
        max_digits=20, decimal_places=0, required=False, allow_null=True
    )
    phone_allowance = FlexibleDecimalField(
        max_digits=20, decimal_places=0, required=False, allow_null=True
    )
    other_allowance = FlexibleDecimalField(
        max_digits=20, decimal_places=0, required=False, allow_null=True
    )
    net_percentage = NetPercentageField(required=False, allow_null=True, allow_blank=True)
    tax_calculation_method = TaxCalculationMethodField(required=False, allow_null=True, allow_blank=True)
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
            raise serializers.ValidationError({
                "sign_date": _("Sign date must be on or before effective date")
            })

        if effective_date and expiration_date and effective_date > expiration_date:
            raise serializers.ValidationError({
                "expiration_date": _("Expiration date must be on or after effective date")
            })

        return attrs


def normalize_header(header: str) -> str:
    """Normalize header name by stripping and lowercasing."""
    if not header:
        return ""
    return str(header).strip().lower()


def normalize_value(value: Any) -> str:
    """Normalize cell value by converting to string and stripping."""
    if value is None:
        return ""
    return str(value).strip()


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


def import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:  # noqa: C901
    """Import handler for contracts.

    Processes a single row from the import file and creates a Contract.
    Uses ContractImportSerializer for parsing and validation.

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

        # Use serializer for parsing and validation
        serializer = ContractImportSerializer(data=row_dict)

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

        # Extract resolved instances from validated data
        employee = validated_data.pop("employee_code")
        contract_type = validated_data.pop("contract_type_code")

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
            "base_salary", "lunch_allowance", "phone_allowance", "other_allowance",
            "net_percentage", "tax_calculation_method", "has_social_insurance",
            "working_conditions", "rights_and_obligations", "terms", "note",
        ]

        for field in optional_fields:
            value = validated_data.get(field)
            if value is not None and value != "":
                contract_data[field] = value

        # Copy snapshot data from contract type for fields not explicitly provided
        copy_snapshot_from_contract_type(contract_type, contract_data)

        # Check for existing contract and handle allow_update
        allow_update = options.get("allow_update", False)

        # Find existing contract by employee + effective_date + contract_type combination
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
                    f"Contract for employee '{employee_code}' with same effective date and contract type already exists (allow_update=False)"
                ],
            }

        # Create or update contract
        with transaction.atomic():
            if existing_contract and allow_update:
                # Update existing contract (only if status is DRAFT)
                if existing_contract.status != Contract.ContractStatus.DRAFT:
                    return {
                        "ok": False,
                        "row_index": row_index,
                        "error": f"Cannot update contract {existing_contract.code}: only DRAFT contracts can be updated",
                        "action": "skipped",
                    }

                for key, value in contract_data.items():
                    if key not in ["employee", "contract_type"]:  # Don't update FK fields
                        setattr(existing_contract, key, value)
                existing_contract.save()
                contract = existing_contract
                action = "updated"
                logger.info(f"Updated contract {contract.code} for employee {employee.code}")
            else:
                # Create new contract
                contract = Contract.objects.create(**contract_data)
                action = "created"
                logger.info(f"Created contract {contract.code} for employee {employee.code}")

        return {
            "ok": True,
            "row_index": row_index,
            "action": action,
            "contract_code": contract.code,
            "warnings": [],
            "result": {
                "contract_id": str(contract.id),
                "contract_code": contract.code,
                "employee_code": employee.code,
            },
        }

    except Exception as e:
        logger.exception(f"Import handler error at row {row_index}: {e}")
        return {
            "ok": False,
            "row_index": row_index,
            "error": str(e),
            "action": "skipped",
        }
