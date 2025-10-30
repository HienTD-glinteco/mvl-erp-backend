"""
Example import handlers for AsyncImportProgressMixin.

This file demonstrates two approaches for creating import handlers:
1. Standalone handler function (can be used across multiple ViewSets)
2. ViewSet method handler (keeps logic close to the ViewSet)
"""


# APPROACH 1: Standalone Handler Function
# =========================================
# This can be reused across multiple ViewSets by referencing the dotted path


def example_import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:
    """
    Example import handler that processes a single row.

    This handler is called for each row in the import file. It should:
    1. Parse and validate the row data
    2. Perform any business logic (create/update database records, etc.)
    3. Return a result dictionary indicating success or failure

    Args:
        row_index: 1-based index of the row in the file (excluding headers)
        row: List of cell values from the row (e.g., ['John', 'Doe', 'john@example.com'])
        import_job_id: UUID string of the ImportJob (for logging/debugging)
        options: Dictionary of import options passed from the API request

    Returns:
        dict: Result dictionary with one of two formats:
            Success: {"ok": True, "result": {"id": 123, ...}}
            Failure: {"ok": False, "error": "Error message"}

    Example row data:
        row = ['John', 'Doe', 'john@example.com', '2025-01-01']
        row_index = 1
        import_job_id = 'a1b2c3d4-...'
        options = {'batch_size': 500, 'custom_option': 'value'}
    """
    try:
        # Example: Parse row data (adjust indices based on your CSV structure)
        first_name = row[0] if len(row) > 0 else None
        last_name = row[1] if len(row) > 1 else None
        email = row[2] if len(row) > 2 else None
        start_date = row[3] if len(row) > 3 else None

        # Validation
        if not email:
            return {"ok": False, "error": "Email is required"}

        if not first_name or not last_name:
            return {"ok": False, "error": "First name and last name are required"}

        # Business logic: Create or update a record
        # (Replace this with your actual model and logic)
        # from apps.myapp.models import MyModel
        #
        # obj, created = MyModel.objects.update_or_create(
        #     email=email,
        #     defaults={
        #         'first_name': first_name,
        #         'last_name': last_name,
        #         'start_date': start_date,
        #     }
        # )

        # For this example, we'll just simulate success
        return {
            "ok": True,
            "result": {
                "id": row_index,  # Replace with actual object ID
                "email": email,
                "action": "created",  # or "updated"
            },
        }

    except Exception as e:
        # Return error for any exceptions
        return {"ok": False, "error": f"Unexpected error: {str(e)}"}


def employee_import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:
    """
    Example handler for importing employees.

    Expected CSV format:
        employee_code, first_name, last_name, email, department, position, hire_date

    Args:
        row_index: 1-based row index
        row: List of cell values
        import_job_id: Import job UUID
        options: Import options

    Returns:
        dict: Success or failure result
    """
    try:
        # Parse columns
        employee_code = row[0] if len(row) > 0 else None
        first_name = row[1] if len(row) > 1 else None
        last_name = row[2] if len(row) > 2 else None
        email = row[3] if len(row) > 3 else None
        department = row[4] if len(row) > 4 else None
        position = row[5] if len(row) > 5 else None
        hire_date_str = row[6] if len(row) > 6 else None

        # Validate required fields
        if not employee_code:
            return {"ok": False, "error": "Employee code is required"}
        if not email:
            return {"ok": False, "error": "Email is required"}

        # Parse date
        from datetime import datetime

        hire_date = None
        if hire_date_str:
            try:
                hire_date = datetime.strptime(str(hire_date_str), "%Y-%m-%d").date()
            except ValueError:
                return {"ok": False, "error": f"Invalid hire date format: {hire_date_str}"}

        # Create or update employee
        # from apps.hrm.models import Employee
        #
        # employee, created = Employee.objects.update_or_create(
        #     employee_code=employee_code,
        #     defaults={
        #         'first_name': first_name,
        #         'last_name': last_name,
        #         'email': email,
        #         'department': department,
        #         'position': position,
        #         'hire_date': hire_date,
        #     }
        # )

        return {
            "ok": True,
            "result": {
                "id": row_index,  # Replace with employee.id
                "employee_code": employee_code,
                "action": "created",  # or "updated"
            },
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


# Additional helper functions can be defined here and used by handlers


def validate_email(email: str) -> bool:
    """Helper function to validate email format."""
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def parse_date(date_str: str, formats: list = None) -> str:
    """
    Helper function to parse date from various formats.

    Args:
        date_str: Date string
        formats: List of date formats to try

    Returns:
        str: ISO formatted date string or None
    """
    from datetime import datetime

    if not formats:
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]

    for fmt in formats:
        try:
            parsed = datetime.strptime(str(date_str), fmt)
            return parsed.date().isoformat()
        except (ValueError, TypeError):
            continue

    return None


# APPROACH 2: ViewSet Method Handler
# ===================================
# This approach keeps the import logic in the ViewSet itself


"""
Example ViewSet with _process_import_data_row method:

from rest_framework.viewsets import ModelViewSet
from apps.imports.api.mixins import AsyncImportProgressMixin


class ProductViewSet(AsyncImportProgressMixin, ModelViewSet):
    '''ViewSet with inline import handler method.'''

    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def _process_import_data_row(self, row_index: int, row: list, import_job_id: str, options: dict) -> dict:
        '''
        Process a single row from product import file.

        This method is automatically detected and used by AsyncImportProgressMixin.
        No need to set import_row_handler attribute.

        Expected CSV format:
            sku, name, price, category

        Args:
            row_index: 1-based row number
            row: List of cell values
            import_job_id: UUID of the import job
            options: Import options from the request

        Returns:
            {"ok": True, "result": {...}} on success
            {"ok": False, "error": "..."} on failure
        '''
        try:
            # Parse row
            sku = row[0] if len(row) > 0 else None
            name = row[1] if len(row) > 1 else None
            price_str = row[2] if len(row) > 2 else None
            category = row[3] if len(row) > 3 else None

            # Validate
            if not sku:
                return {"ok": False, "error": "SKU is required"}
            if not name:
                return {"ok": False, "error": "Name is required"}

            # Parse price
            from decimal import Decimal, InvalidOperation
            try:
                price = Decimal(price_str) if price_str else None
            except InvalidOperation:
                return {"ok": False, "error": f"Invalid price: {price_str}"}

            # Create or update product
            from apps.products.models import Product
            product, created = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'price': price,
                    'category': category,
                }
            )

            return {
                "ok": True,
                "result": {
                    "id": product.id,
                    "action": "created" if created else "updated"
                }
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}


# COMPARISON OF APPROACHES
# ========================

# Use Standalone Handler Function when:
# - Handler logic is complex and needs to be tested independently
# - Same handler is used across multiple ViewSets
# - You want to keep ViewSet code clean and focused on API logic
# - Handler needs to be shared or reused in other contexts

# Use ViewSet Method Handler when:
# - Import logic is simple and specific to one ViewSet
# - You want to keep all related code in one place
# - Handler needs access to ViewSet state or methods
# - You prefer inline definition for simplicity
"""
