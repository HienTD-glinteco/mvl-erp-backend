"""
Example: Using ImportXLSXMixin with a ViewSet

This example demonstrates how to add XLSX import functionality to a ViewSet.
"""

from apps.audit_logging.api.mixins import AuditLoggingMixin
from libs import BaseModelViewSet, ImportXLSXMixin


# Example 1: Basic Usage with Auto Schema
class DepartmentViewSet(ImportXLSXMixin, BaseModelViewSet):
    """
    ViewSet for Department with import functionality.

    This ViewSet automatically provides:
    - Standard CRUD endpoints
    - /import/ endpoint for XLSX import
    - Auto-generated import schema from model fields
    """

    queryset = None  # Set to Department.objects.all()
    serializer_class = None  # Set to DepartmentSerializer
    module = "Organization"
    submodule = "Department Management"
    permission_prefix = "department"


# Example 2: Import with Audit Logging
class EmployeeViewSet(AuditLoggingMixin, ImportXLSXMixin, BaseModelViewSet):
    """
    ViewSet with both import and audit logging.

    IMPORTANT: Mixin order matters!
    - AuditLoggingMixin must come BEFORE ImportXLSXMixin
    """

    module = "HR"
    submodule = "Employee Management"
    permission_prefix = "employee"


# Example 3: Custom Import Schema
class ProjectViewSet(ImportXLSXMixin, BaseModelViewSet):
    """ViewSet with custom import schema"""

    module = "Projects"
    submodule = "Project Management"
    permission_prefix = "project"

    def get_import_schema(self, request, file):
        """Custom import schema"""
        return {
            "fields": ["name", "start_date", "budget"],
            "required": ["name", "start_date"],
        }
