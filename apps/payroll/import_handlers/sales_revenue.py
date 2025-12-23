"""Import handler for sales revenue data."""

from datetime import date

from apps.hrm.models import Employee
from apps.payroll.models import SalesRevenue


def process_sales_revenue_row(row_index: int, row: dict, import_job_id: int, options: dict) -> dict:  # noqa: C901
    """Process a single sales revenue row from import file.

    Args:
        row_index: Row number in the file (1-based)
        row: Dictionary containing row data with keys from header
        import_job_id: ID of the ImportJob
        options: Dictionary containing:
            - target_month: date object for the target month

    Returns:
        Dictionary with:
            - ok: bool indicating success
            - result: dict with created/updated object data on success
            - error: str with error message on failure
    """
    try:
        # Extract target month from options
        target_month = options.get("target_month")
        if not target_month:
            return {"ok": False, "error": "Target month not provided in options"}

        # Extract fields from row
        employee_code = str(row.get("Mã nhân viên", "")).strip() if row.get("Mã nhân viên") else ""
        revenue_raw = row.get("Doanh Số", 0)
        transaction_count_raw = row.get("Số giao dịch", 0)
        month_str = str(row.get("Thời gian", "")).strip() if row.get("Thời gian") else ""

        # Validate employee code
        if not employee_code:
            return {"ok": False, "error": "Employee code is required"}

        # Get employee
        try:
            employee = Employee.objects.get(code=employee_code)
        except Employee.DoesNotExist:
            return {"ok": False, "error": f"Employee not found: {employee_code}"}

        # Validate and parse month if provided
        row_month = target_month
        if month_str:
            try:
                parts = month_str.split("/")
                if len(parts) != 2:
                    raise ValueError("Invalid format")
                month = int(parts[0])
                year = int(parts[1])
                row_month = date(year, month, 1)

                # Check if month matches target
                if row_month != target_month:
                    return {
                        "ok": False,
                        "error": f"Month {month_str} does not match target month {target_month.month:02d}/{target_month.year}",
                    }
            except (ValueError, TypeError, IndexError):
                return {"ok": False, "error": "Invalid month format, expected MM/YYYY"}

        # Parse numeric fields
        try:
            revenue = int(float(revenue_raw)) if revenue_raw else 0
            transaction_count = int(float(transaction_count_raw)) if transaction_count_raw else 0
        except (ValueError, TypeError):
            return {"ok": False, "error": "Invalid revenue or transaction count"}

        # Validate values
        if revenue < 0:
            return {"ok": False, "error": "Revenue must be non-negative"}
        if transaction_count < 0:
            return {"ok": False, "error": "Transaction count must be non-negative"}

        # Create or update record
        obj, created = SalesRevenue.objects.update_or_create(
            employee=employee,
            month=row_month,
            defaults={
                "revenue": revenue,
                "transaction_count": transaction_count,
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
