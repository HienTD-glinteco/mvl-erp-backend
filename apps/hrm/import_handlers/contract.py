"""Import handler for Contract model."""

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

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


def parse_date(value: Any, field_name: str) -> tuple[date | None, str | None]:
    """Parse date from various formats.

    Args:
        value: Date value (string, date, or datetime)
        field_name: Name of field for error messages

    Returns:
        Tuple of (date_object, error_message)
    """
    if not value:
        return None, None

    # If already a date object
    if isinstance(value, date):
        return value, None

    # If datetime object
    if isinstance(value, datetime):
        return value.date(), None

    # Try parsing string
    value_str = str(value).strip()
    if not value_str or value_str == "-":
        return None, None

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value_str, fmt)
            return parsed.date(), None
        except (ValueError, TypeError):
            continue

    return None, f"Invalid date format for {field_name}: {value_str}"


def parse_decimal(value: Any, field_name: str) -> tuple[Decimal | None, str | None]:
    """Parse decimal value.

    Args:
        value: Decimal value (string or number)
        field_name: Name of field for error messages

    Returns:
        Tuple of (decimal_value, error_message)
    """
    if value is None or str(value).strip() == "":
        return None, None

    try:
        # Remove common formatting characters
        value_str = str(value).strip()
        value_str = value_str.replace(",", "").replace(" ", "")
        return Decimal(value_str), None
    except InvalidOperation:
        return None, f"Invalid decimal value for {field_name}: {value}"


def parse_boolean(value: Any, field_name: str) -> tuple[bool | None, str | None]:
    """Parse boolean value.

    Args:
        value: Boolean value (string or bool)
        field_name: Name of field for error messages

    Returns:
        Tuple of (bool_value, error_message)
    """
    if value is None or str(value).strip() == "":
        return None, None

    if isinstance(value, bool):
        return value, None

    value_str = str(value).strip().lower()
    if value_str in BOOLEAN_MAPPING:
        return BOOLEAN_MAPPING[value_str], None

    return None, f"Invalid boolean value for {field_name}: {value}"


def lookup_employee(code: str) -> tuple[Employee | None, str | None]:
    """Lookup employee by code.

    Args:
        code: Employee code

    Returns:
        Tuple of (Employee instance or None, error_message)
    """
    if not code:
        return None, "Employee code is required"

    employee = Employee.objects.filter(code__iexact=code.strip()).first()
    if not employee:
        return None, f"Employee with code '{code}' not found"

    return employee, None


def lookup_contract_type(code: str) -> tuple[ContractType | None, str | None]:
    """Lookup contract type by code.

    Args:
        code: Contract type code

    Returns:
        Tuple of (ContractType instance or None, error_message)
    """
    if not code:
        return None, "Contract type code is required"

    contract_type = ContractType.objects.filter(code__iexact=code.strip()).first()
    if not contract_type:
        return None, f"Contract type with code '{code}' not found"

    return contract_type, None


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
    warnings = []

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

        # Map row to dictionary
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(row):
                normalized_header = normalize_header(header)
                field_name = COLUMN_MAPPING.get(normalized_header, normalized_header)
                row_dict[field_name] = row[i]

        # Extract required values
        employee_code = normalize_value(row_dict.get("employee_code", ""))
        contract_type_code = normalize_value(row_dict.get("contract_type_code", ""))

        # Skip row if missing required fields
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
                "contract_code": None,
                "warnings": ["Missing required field: contract type code"],
            }

        # Lookup employee
        employee, employee_error = lookup_employee(employee_code)
        if employee_error:
            return {
                "ok": False,
                "row_index": row_index,
                "error": employee_error,
                "action": "skipped",
            }

        # Lookup contract type
        contract_type, contract_type_error = lookup_contract_type(contract_type_code)
        if contract_type_error:
            return {
                "ok": False,
                "row_index": row_index,
                "error": contract_type_error,
                "action": "skipped",
            }

        # Parse dates
        sign_date_raw = row_dict.get("sign_date")
        sign_date, sign_date_error = parse_date(sign_date_raw, "sign_date")
        if sign_date_error:
            return {
                "ok": False,
                "row_index": row_index,
                "error": sign_date_error,
                "action": "skipped",
            }

        effective_date_raw = row_dict.get("effective_date")
        effective_date, effective_date_error = parse_date(effective_date_raw, "effective_date")
        if effective_date_error:
            return {
                "ok": False,
                "row_index": row_index,
                "error": effective_date_error,
                "action": "skipped",
            }

        expiration_date_raw = row_dict.get("expiration_date")
        expiration_date, expiration_date_error = parse_date(expiration_date_raw, "expiration_date")
        if expiration_date_error:
            return {
                "ok": False,
                "row_index": row_index,
                "error": expiration_date_error,
                "action": "skipped",
            }

        # Validate required dates
        if not sign_date:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Sign date is required",
                "action": "skipped",
            }

        if not effective_date:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Effective date is required",
                "action": "skipped",
            }

        # Validate date logic
        if sign_date > effective_date:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Sign date must be on or before effective date",
                "action": "skipped",
            }

        if expiration_date and effective_date > expiration_date:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Expiration date must be on or after effective date",
                "action": "skipped",
            }

        # Build contract data
        contract_data = {
            "employee": employee,
            "contract_type": contract_type,
            "sign_date": sign_date,
            "effective_date": effective_date,
            "expiration_date": expiration_date,
            "status": DEFAULT_STATUS,
        }

        # Parse optional numeric fields
        base_salary_raw = row_dict.get("base_salary")
        if base_salary_raw:
            base_salary, salary_error = parse_decimal(base_salary_raw, "base_salary")
            if salary_error:
                warnings.append(salary_error)
            elif base_salary is not None:
                contract_data["base_salary"] = base_salary

        lunch_allowance_raw = row_dict.get("lunch_allowance")
        if lunch_allowance_raw:
            lunch_allowance, lunch_error = parse_decimal(lunch_allowance_raw, "lunch_allowance")
            if lunch_error:
                warnings.append(lunch_error)
            elif lunch_allowance is not None:
                contract_data["lunch_allowance"] = lunch_allowance

        phone_allowance_raw = row_dict.get("phone_allowance")
        if phone_allowance_raw:
            phone_allowance, phone_error = parse_decimal(phone_allowance_raw, "phone_allowance")
            if phone_error:
                warnings.append(phone_error)
            elif phone_allowance is not None:
                contract_data["phone_allowance"] = phone_allowance

        other_allowance_raw = row_dict.get("other_allowance")
        if other_allowance_raw:
            other_allowance, other_error = parse_decimal(other_allowance_raw, "other_allowance")
            if other_error:
                warnings.append(other_error)
            elif other_allowance is not None:
                contract_data["other_allowance"] = other_allowance

        # Parse net percentage
        net_percentage_raw = normalize_value(row_dict.get("net_percentage", "")).lower()
        if net_percentage_raw and net_percentage_raw in NET_PERCENTAGE_MAPPING:
            contract_data["net_percentage"] = NET_PERCENTAGE_MAPPING[net_percentage_raw]
        elif net_percentage_raw:
            warnings.append(f"Unknown net percentage: {net_percentage_raw}, using default from contract type")

        # Parse tax calculation method
        tax_method_raw = normalize_value(row_dict.get("tax_calculation_method", "")).lower()
        if tax_method_raw and tax_method_raw in TAX_CALCULATION_MAPPING:
            contract_data["tax_calculation_method"] = TAX_CALCULATION_MAPPING[tax_method_raw]
        elif tax_method_raw:
            warnings.append(f"Unknown tax calculation method: {tax_method_raw}, using default from contract type")

        # Parse has_social_insurance
        has_insurance_raw = row_dict.get("has_social_insurance")
        if has_insurance_raw:
            has_insurance, insurance_error = parse_boolean(has_insurance_raw, "has_social_insurance")
            if insurance_error:
                warnings.append(insurance_error)
            elif has_insurance is not None:
                contract_data["has_social_insurance"] = has_insurance

        # Parse text fields
        working_conditions = normalize_value(row_dict.get("working_conditions", ""))
        if working_conditions:
            contract_data["working_conditions"] = working_conditions

        rights_and_obligations = normalize_value(row_dict.get("rights_and_obligations", ""))
        if rights_and_obligations:
            contract_data["rights_and_obligations"] = rights_and_obligations

        terms = normalize_value(row_dict.get("terms", ""))
        if terms:
            contract_data["terms"] = terms

        note = normalize_value(row_dict.get("note", ""))
        if note:
            contract_data["note"] = note

        # Copy snapshot data from contract type for fields not explicitly provided
        copy_snapshot_from_contract_type(contract_type, contract_data)

        # Check for existing contract and handle allow_update
        allow_update = options.get("allow_update", False)

        # Find existing contract by employee + effective_date combination
        # or by employee + contract_type if within a reasonable time frame
        existing_contract = Contract.objects.filter(
            employee=employee,
            effective_date=effective_date,
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
            "warnings": warnings,
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
