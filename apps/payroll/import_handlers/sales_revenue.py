"""Import handler for sales revenue data."""

import logging
from datetime import date

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import Employee
from apps.payroll.models import SalesRevenue
from apps.payroll.tasks import aggregate_sales_revenue_report_task

logger = logging.getLogger(__name__)


def _parse_target_month(target_month_str: str) -> date | None:
    """Parse target month string (MM/YYYY format) to date.

    Args:
        target_month_str: Month string in MM/YYYY format

    Returns:
        Date object representing first day of month, or None if invalid
    """
    try:
        parts = str(target_month_str).split("/")
        if len(parts) != 2:
            return None
        target_month_num = int(parts[0])
        target_year = int(parts[1])
        return date(target_year, target_month_num, 1)
    except (ValueError, TypeError, IndexError):
        return None


class SalesRevenueImportRowSerializer(serializers.Serializer):
    """Serializer for validating sales revenue import row data.

    Handles validation of raw Excel row data with Vietnamese column names.
    Validates:
        - Employee code exists and maps to valid employee
        - Month matches target month from import options
        - Numeric fields (kpi_target, revenue, transaction_count) are valid
    """

    employee_code = serializers.CharField(
        required=True,
        allow_blank=False,
        min_length=1,
        max_length=20,
        error_messages={"required": _("Employee code is required"), "blank": _("Employee code is required")},
    )
    kpi_target = serializers.CharField(
        required=True,
        allow_blank=False,
        min_length=1,
        max_length=20,
        error_messages={"required": _("KPI target is required"), "blank": _("KPI target is required")},
    )
    revenue = serializers.CharField(
        required=True,
        allow_blank=False,
        min_length=1,
        max_length=20,
        error_messages={"required": _("Revenue is required"), "blank": _("Revenue is required")},
    )
    transaction_count = serializers.CharField(
        required=True,
        allow_blank=False,
        min_length=1,
        max_length=20,
        error_messages={
            "required": _("Transaction count is required"),
            "blank": _("Transaction count is required"),
        },
    )
    month = serializers.CharField(
        required=True,
        allow_blank=False,
    )

    def __init__(self, *args, target_month: date | None = None, **kwargs):
        """Initialize serializer with target month context."""
        super().__init__(*args, **kwargs)
        self.target_month = target_month

    def validate_employee_code(self, value: str) -> Employee:
        """Validate employee code and return Employee instance."""
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError(_("Employee code is required"))

        try:
            return Employee.objects.get(code=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError(_("Employee not found: %(code)s") % {"code": value})

    def validate_kpi_target(self, value) -> int:
        """Validate and parse KPI target to integer."""
        try:
            parsed = int(float(value)) if value else 0
            if parsed < 0:
                raise serializers.ValidationError(_("KPI target must be non-negative"))
            return parsed
        except (ValueError, TypeError):
            raise serializers.ValidationError(_("Invalid KPI target value"))

    def validate_revenue(self, value) -> int:
        """Validate and parse revenue to integer."""
        try:
            parsed = int(float(value)) if value else 0
            if parsed < 0:
                raise serializers.ValidationError(_("Revenue must be non-negative"))
            return parsed
        except (ValueError, TypeError):
            raise serializers.ValidationError(_("Invalid revenue or transaction count"))

    def validate_transaction_count(self, value) -> int:
        """Validate and parse transaction count to integer."""
        try:
            parsed = int(float(value)) if value else 0
            if parsed < 0:
                raise serializers.ValidationError(_("Transaction count must be non-negative"))
            return parsed
        except (ValueError, TypeError):
            raise serializers.ValidationError(_("Invalid revenue or transaction count"))

    def validate_month(self, value: str) -> date | None:
        """Validate month format (MM/YYYY) and return date."""
        value = str(value).strip() if value else ""
        parsed_date = _parse_target_month(value)
        if not parsed_date:
            raise serializers.ValidationError(_("Invalid month format, expected MM/YYYY"))
        return parsed_date

    def validate(self, data: dict) -> dict:
        """Cross-field validation: ensure row month matches target month."""
        row_month: date | None = data.get("month")

        if self.target_month and row_month and row_month != self.target_month:
            raise serializers.ValidationError(
                _("Month %(row_month)s does not match target month %(target_month)s")
                % {
                    "row_month": f"{row_month.month:02d}/{row_month.year}",
                    "target_month": f"{self.target_month.month:02d}/{self.target_month.year}",
                }
            )

        return data


def process_sales_revenue_row(row_index: int, row: list | tuple, import_job_id: int, options: dict) -> dict:
    """Process a single sales revenue row from import file.

    Args:
        row_index: Row number in the file (1-based)
        row: List/tuple of row values from Excel file
        import_job_id: ID of the ImportJob
        options: Dictionary containing:
            - headers: List of column headers from Excel file
            - handler_options: Dict with target_month

    Returns:
        Dictionary with:
            - ok: bool indicating success
            - result: dict with created/updated object data on success
            - error: str with error message on failure
    """
    try:
        # Map row list to dict using headers
        headers = options.get("headers", [])
        if not headers:
            return {"ok": False, "error": _("Headers not found in options")}

        row_dict = dict(zip(headers, row, strict=False))

        # Extract and parse target month from options
        target_month_str = options.get("handler_options", {}).get("target_month")
        if not target_month_str:
            return {"ok": False, "error": _("Target month not provided in options")}

        target_month = _parse_target_month(target_month_str)
        if not target_month:
            return {"ok": False, "error": _("Invalid target month format, expected MM/YYYY")}

        # Map Vietnamese column names to serializer fields
        raw_data = {
            "employee_code": row_dict.get("Mã nhân viên", ""),
            "kpi_target": row_dict.get("Chỉ tiêu", ""),
            "revenue": row_dict.get("Doanh Số", ""),
            "transaction_count": row_dict.get("Số giao dịch", ""),
            "month": row_dict.get("Thời gian", ""),
        }

        # Validate using serializer
        serializer = SalesRevenueImportRowSerializer(data=raw_data, target_month=target_month)
        if not serializer.is_valid():
            # Format first error message
            errors = serializer.errors
            for field, field_errors in errors.items():
                if field_errors:
                    error_msg = field_errors[0] if isinstance(field_errors, list) else str(field_errors)
                    return {"ok": False, "error": str(error_msg)}
            return {"ok": False, "error": _("Validation failed")}

        validated = serializer.validated_data
        employee = validated["employee_code"]  # Returns Employee instance
        row_month = validated["month"]
        revenue = validated["revenue"]
        transaction_count = validated["transaction_count"]
        kpi_target = validated["kpi_target"]

        # Create or update record
        obj, created = SalesRevenue.objects.update_or_create(
            employee=employee,
            month=row_month,
            defaults={
                "revenue": revenue,
                "transaction_count": transaction_count,
                "kpi_target": kpi_target,
                "status": SalesRevenue.SalesRevenueStatus.NOT_CALCULATED,
            },
        )

        return {
            "ok": True,
            "result": {
                "id": obj.id,
                "code": obj.code,
                "employee_code": employee.code,
                "revenue": revenue,
                "transaction_count": transaction_count,
                "action": "created" if created else "updated",
            },
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def on_import_complete(import_job_id: int, options: dict) -> None:
    """Called after import completes successfully to trigger report aggregation.

    Uses Celery task to run aggregation in background, not blocking the import.

    Args:
        import_job_id: ID of the completed ImportJob
        options: Import options dictionary
    """
    # Trigger aggregation in background
    target_month_str = options.get("target_month")
    target_month_iso = None

    if not target_month_str:
        logger.error("Target month not provided in options for import job %s", import_job_id)
        return

    target_month = _parse_target_month(target_month_str)
    if not target_month:
        logger.error(
            "Invalid target month format '%s' in options for import job %s",
            target_month_str,
            import_job_id,
        )
        return

    target_month_iso = target_month.isoformat()
    aggregate_sales_revenue_report_task.delay(target_month_iso)
