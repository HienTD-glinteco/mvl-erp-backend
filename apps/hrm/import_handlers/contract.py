"""Import handler for Contract model."""

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
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

# Boolean mapping for has_social_insurance
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


def preprocess_date(value: Any) -> date | str | None:
    """Preprocess date value before passing to serializer.

    Args:
        value: Date value (string, date, or datetime)

    Returns:
        date object, ISO string, or None
    """
    if not value:
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    value_str = str(value).strip()
    if not value_str or value_str == "-":
        return None

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value_str, fmt).date()
        except (ValueError, TypeError):
            continue

    return value_str


def preprocess_decimal(value: Any) -> Decimal | str | None:
    """Preprocess decimal value with comma as decimal separator.

    Args:
        value: Decimal value (string or number)

    Returns:
        Decimal object, string, or None
    """
    if value is None:
        return None

    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    value_str = str(value).strip()
    if not value_str:
        return None

    try:
        # Replace comma with dot for decimal separator
        value_str = value_str.replace(",", ".")
        return Decimal(value_str)
    except InvalidOperation:
        return value_str


def preprocess_boolean(value: Any) -> bool | None:
    """Preprocess boolean value with Vietnamese support.

    Args:
        value: Boolean value (string or bool)

    Returns:
        bool or None
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    value_str = str(value).strip().lower()
    if not value_str:
        return None

    return BOOLEAN_MAPPING.get(value_str)


def preprocess_net_percentage(value: Any) -> str | None:
    """Preprocess net percentage value."""
    if value is None:
        return None

    value_str = str(value).strip().lower()
    if not value_str:
        return None

    if value_str in NET_PERCENTAGE_MAPPING:
        return NET_PERCENTAGE_MAPPING[value_str]

    return None


def preprocess_tax_method(value: Any) -> str | None:
    """Preprocess tax calculation method value."""
    if value is None:
        return None

    value_str = str(value).strip().lower()
    if not value_str:
        return None

    if value_str in TAX_CALCULATION_MAPPING:
        return TAX_CALCULATION_MAPPING[value_str]

    return None


class ContractImportSerializer(serializers.Serializer):
    """Serializer for contract import row data.

    Handles validation of import row data using standard DRF fields.
    """

    # Required fields - employee and contract_type are resolved instances
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    contract_type = serializers.PrimaryKeyRelatedField(queryset=ContractType.objects.all())
    sign_date = serializers.DateField()
    effective_date = serializers.DateField()

    # Optional fields
    expiration_date = serializers.DateField(required=False, allow_null=True)
    base_salary = serializers.DecimalField(
        max_digits=20, decimal_places=0, required=False, allow_null=True
    )
    lunch_allowance = serializers.DecimalField(
        max_digits=20, decimal_places=0, required=False, allow_null=True
    )
    phone_allowance = serializers.DecimalField(
        max_digits=20, decimal_places=0, required=False, allow_null=True
    )
    other_allowance = serializers.DecimalField(
        max_digits=20, decimal_places=0, required=False, allow_null=True
    )
    net_percentage = serializers.ChoiceField(
        choices=ContractType.NetPercentage.choices, required=False, allow_null=True
    )
    tax_calculation_method = serializers.ChoiceField(
        choices=ContractType.TaxCalculationMethod.choices, required=False, allow_null=True
    )
    has_social_insurance = serializers.BooleanField(required=False, allow_null=True)
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
    Uses ContractImportSerializer for validation.

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

        # Lookup employee and contract type
        employee = Employee.objects.filter(code__iexact=employee_code).first()
        if not employee:
            return {
                "ok": False,
                "row_index": row_index,
                "error": f"Employee with code '{employee_code}' not found",
                "action": "skipped",
            }

        contract_type = ContractType.objects.filter(code__iexact=contract_type_code).first()
        if not contract_type:
            return {
                "ok": False,
                "row_index": row_index,
                "error": f"Contract type with code '{contract_type_code}' not found",
                "action": "skipped",
            }

        # Preprocess raw values before passing to serializer
        serializer_data = {
            "employee": employee.pk,
            "contract_type": contract_type.pk,
            "sign_date": preprocess_date(row_dict.get("sign_date")),
            "effective_date": preprocess_date(row_dict.get("effective_date")),
            "expiration_date": preprocess_date(row_dict.get("expiration_date")),
            "base_salary": preprocess_decimal(row_dict.get("base_salary")),
            "lunch_allowance": preprocess_decimal(row_dict.get("lunch_allowance")),
            "phone_allowance": preprocess_decimal(row_dict.get("phone_allowance")),
            "other_allowance": preprocess_decimal(row_dict.get("other_allowance")),
            "net_percentage": preprocess_net_percentage(row_dict.get("net_percentage")),
            "tax_calculation_method": preprocess_tax_method(row_dict.get("tax_calculation_method")),
            "has_social_insurance": preprocess_boolean(row_dict.get("has_social_insurance")),
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
            "employee": validated_data["employee"],
            "contract_type": validated_data["contract_type"],
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
                if existing_contract.status != Contract.ContractStatus.DRAFT:
                    return {
                        "ok": False,
                        "row_index": row_index,
                        "error": f"Cannot update contract {existing_contract.code}: only DRAFT contracts can be updated",
                        "action": "skipped",
                    }

                for key, value in contract_data.items():
                    if key not in ["employee", "contract_type"]:
                        setattr(existing_contract, key, value)
                existing_contract.save()
                contract = existing_contract
                action = "updated"
                logger.info(f"Updated contract {contract.code} for employee {employee.code}")
            else:
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
