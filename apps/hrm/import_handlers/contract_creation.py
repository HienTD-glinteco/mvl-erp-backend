"""Import handler for Contract creation."""

import logging

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.constants import EmployeeType
from apps.hrm.models import Contract, ContractType, Employee, EmployeeWorkHistory
from libs.drf.serializers import (
    FlexibleBooleanField,
    FlexibleChoiceField,
    FlexibleDateField,
    FlexibleDecimalField,
    normalize_value,
)
from libs.strings import normalize_header

logger = logging.getLogger(__name__)

# Column mapping for import template
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
    "loại nhân viên": "employee_type",
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

# Employee Type Mapping
EMPLOYEE_TYPE_MAPPING = {
    "thử việc": EmployeeType.PROBATION,
    "chính thức": EmployeeType.OFFICIAL,
    "thực tập": EmployeeType.INTERN,
    "cộng tác viên": EmployeeType.APPRENTICE, # Mapping 'cộng tác viên' to APPRENTICE as best fit, or need verification
    "part-time": EmployeeType.PROBATION_TYPE_1, # Placeholder, checking constants for best fit
}
# Re-checking constants from file:
# OFFICIAL, APPRENTICE, UNPAID_OFFICIAL, UNPAID_PROBATION, PROBATION, INTERN, PROBATION_TYPE_1
# Correction:
EMPLOYEE_TYPE_MAPPING = {
    "thử việc": EmployeeType.PROBATION,
    "chính thức": EmployeeType.OFFICIAL,
    "thực tập": EmployeeType.INTERN,
    "học việc": EmployeeType.APPRENTICE,
    # "cộng tác viên": ... no direct map, maybe APPRENTICE?
    # Keeping safe mapping based on available constants
}


class ContractCreationImportSerializer(serializers.Serializer):
    """Serializer for contract creation import row data."""

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
    content = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")
    employee_type = FlexibleChoiceField(
        choices=EmployeeType.choices,
        value_mapping=EMPLOYEE_TYPE_MAPPING,
        required=False,
        allow_null=True,
    )

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
    """Copy snapshot data from ContractType to contract data."""
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

    logger.info(
        "Import job %s: Prefetched %d employees and %d contract types",
        import_job_id,
        len(employees_by_code),
        len(contract_types_by_code),
    )


def import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:  # noqa: C901
    """Import handler for creating new contracts."""
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

        employees_by_code = options.get("_employees_by_code", {})
        # Note: employee_code from row_dict might be case-sensitive depending on input, but dict keys are lower
        employee = employees_by_code.get(str(employee_code).lower())
        if not employee:
            # Fallback for testing environment where objects might not be in the prefetched dictionary
            # Try case-insensitive lookup
            employee = Employee.objects.filter(code__iexact=str(employee_code)).first()
            if not employee:
                logger.error("Employee not found in options: %s. Keys: %s", employee_code, employees_by_code.keys())
                return {
                    "ok": False,
                    "row_index": row_index,
                    "error": "Employee with code '%s' not found" % employee_code,
                    "action": "skipped",
                }

        contract_types_by_code = options.get("_contract_types_by_code", {})
        contract_type = contract_types_by_code.get(str(contract_type_code).lower())
        if not contract_type:
            # Fallback for testing environment
            contract_type = ContractType.objects.filter(code__iexact=str(contract_type_code)).first()
            if not contract_type:
                return {
                    "ok": False,
                    "row_index": row_index,
                    "error": "Contract type with code '%s' not found" % contract_type_code,
                    "action": "skipped",
                }

        if contract_type.category != ContractType.Category.CONTRACT:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Invalid contract type category. Expected 'contract', got '%s'" % contract_type.category,
                "action": "skipped",
            }

        # Parse data
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
            "content": normalize_value(row_dict.get("content", "")),
            "note": normalize_value(row_dict.get("note", "")),
            "employee_type": row_dict.get("employee_type"),
        }

        serializer = ContractCreationImportSerializer(data=serializer_data)
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

        # DUPLICATE CHECK: Employee + ContractType + EffectiveDate
        # We check for any contract (Draft or Active) to prevent creating duplicates in this run.
        # DUPLICATE CHECK: Employee + ContractType + EffectiveDate
        # We check for any contract (Draft or Active) to prevent creating duplicates in this run.
        duplicate = Contract.objects.filter(
            employee=employee,
            contract_type=contract_type,
            effective_date=validated_data["effective_date"],
        ).first()

        if duplicate:
             logger.warning(
                 "Duplicate found: Emp %s, CT %s, Date %s. Existing ID: %s",
                 employee.code, contract_type.code, validated_data["effective_date"], duplicate.id
             )
             return {
                "ok": False,
                "row_index": row_index,
                "error": "Duplicate contract found for Employee + ContractType + EffectiveDate",
                "action": "skipped",
            }

        contract_data = {
            "employee": employee,
            "contract_type": contract_type,
            "sign_date": validated_data["sign_date"],
            "effective_date": validated_data["effective_date"],
            "expiration_date": validated_data.get("expiration_date"),
            # Status will be calculated below
        }

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
            "content",
            "note",
        ]

        for field in optional_fields:
            value = validated_data.get(field)
            if value is not None and value != "":
                contract_data[field] = value

        copy_snapshot_from_contract_type(contract_type, contract_data)

        # Create Contract and Side Effects
        try:
            with transaction.atomic():
                # Create instance first to call methods on it, but save last
                contract = Contract(**contract_data)

                # Auto-calculate status
                contract.status = contract.get_status_from_dates()
                try:
                    contract.save()
                except Exception as e:
                    logger.error("Error saving contract: %s. Data: %s", e, contract_data)
                    raise e

                # Side effect 1: Update Employee Type
                new_employee_type = validated_data.get("employee_type")
                if new_employee_type and employee.employee_type != new_employee_type:
                    employee.employee_type = new_employee_type
                    employee.save(update_fields=["employee_type"])

                # Side effect 2: Create Work History
                EmployeeWorkHistory.objects.create(
                    employee=employee,
                    date=contract.effective_date,
                    name=EmployeeWorkHistory.EventType.CHANGE_CONTRACT,
                    contract=contract,
                    # Copy Org fields from current employee state
                    branch=employee.branch,
                    block=employee.block,
                    department=employee.department,
                    position=employee.position,
                    note=f"Imported contract {contract.code}",
                )

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
            # Re-raise to catch block below
             raise e

    except Exception as e:
        logger.exception("Import handler error at row %d: %s", row_index, e)
        return {
            "ok": False,
            "row_index": row_index,
            "error": str(e),
            "action": "skipped",
        }
