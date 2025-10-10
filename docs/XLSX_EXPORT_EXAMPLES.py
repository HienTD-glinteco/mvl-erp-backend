"""
XLSX Export Feature - Code Examples

This file contains practical examples of using the XLSX export feature.
Copy and adapt these examples to your own ViewSets.
"""

# ============================================================================
# Example 1: Basic Export (Auto-generated Schema)
# ============================================================================

from rest_framework import viewsets

from libs.export_xlsx import ExportXLSXMixin

from apps.core.models import Role
from apps.core.api.serializers import RoleSerializer


class RoleViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    """
    Simple ViewSet with auto-generated export.

    The mixin automatically creates a /export/ endpoint that exports
    all Role fields (excluding id, created_at, updated_at).

    Usage:
        GET /api/roles/export/
    """

    queryset = Role.objects.all()
    serializer_class = RoleSerializer


# ============================================================================
# Example 2: Custom Single Sheet Export
# ============================================================================


class ProjectViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    """
    ViewSet with custom export schema.

    Overrides get_export_data to provide custom field selection and formatting.
    """

    queryset = None  # Project.objects.all()
    serializer_class = None

    def get_export_data(self, request):
        """Export projects with selected fields."""
        queryset = self.filter_queryset(self.get_queryset())

        data = []
        for project in queryset:
            data.append(
                {
                    "name": project.name,
                    "start_date": project.start_date.strftime("%Y-%m-%d"),
                    "end_date": project.end_date.strftime("%Y-%m-%d") if project.end_date else "",
                    "budget": f"${project.budget:,.2f}",
                    "status": project.get_status_display(),
                }
            )

        return {
            "sheets": [
                {
                    "name": "Projects",
                    "headers": ["Project Name", "Start Date", "End Date", "Budget", "Status"],
                    "field_names": ["name", "start_date", "end_date", "budget", "status"],
                    "data": data,
                }
            ]
        }


# ============================================================================
# Example 3: Multi-Sheet Export
# ============================================================================


class ReportViewSet(ExportXLSXMixin, viewsets.ViewSet):
    """
    ViewSet exporting data to multiple sheets.

    Creates separate sheets for different data categories.
    """

    def get_export_data(self, request):
        """Export summary and detailed data to separate sheets."""
        # projects = Project.objects.all()
        # tasks = Task.objects.select_related('project').all()

        # Sheet 1: Project Summary
        project_data = [
            {"name": "Project A", "tasks_count": 10, "budget": 50000, "status": "Active"},
            {"name": "Project B", "tasks_count": 5, "budget": 30000, "status": "Completed"},
        ]

        # Sheet 2: Task Details
        task_data = [
            {"project": "Project A", "task": "Design", "hours": 40, "status": "Done"},
            {"project": "Project A", "task": "Development", "hours": 120, "status": "In Progress"},
            {"project": "Project B", "task": "Testing", "hours": 30, "status": "Done"},
        ]

        return {
            "sheets": [
                {
                    "name": "Project Summary",
                    "headers": ["Project Name", "Total Tasks", "Budget", "Status"],
                    "field_names": ["name", "tasks_count", "budget", "status"],
                    "data": project_data,
                },
                {
                    "name": "Task Details",
                    "headers": ["Project", "Task Name", "Hours", "Status"],
                    "field_names": ["project", "task", "hours", "status"],
                    "data": task_data,
                },
            ]
        }


# ============================================================================
# Example 4: Nested Data with Merged Cells
# ============================================================================


class ProjectTaskViewSet(ExportXLSXMixin, viewsets.ViewSet):
    """
    ViewSet with hierarchical data export.

    Uses merge_rules to visually group related data.
    """

    def get_export_data(self, request):
        """
        Export projects with their tasks and materials.

        Merged cells make it easy to see which tasks belong to which project.
        """
        # Flatten nested structure
        rows = []

        # Example: Project A with 2 tasks, each task with materials
        rows.extend(
            [
                {
                    "project": "Building A",
                    "task": "Foundation",
                    "task_status": "Completed",
                    "material": "Cement",
                    "quantity": 500,
                    "unit": "kg",
                    "cost": 1200,
                },
                {
                    "project": "Building A",
                    "task": "Foundation",
                    "task_status": "Completed",
                    "material": "Steel",
                    "quantity": 200,
                    "unit": "kg",
                    "cost": 800,
                },
                {
                    "project": "Building A",
                    "task": "Framing",
                    "task_status": "In Progress",
                    "material": "Wood",
                    "quantity": 300,
                    "unit": "pcs",
                    "cost": 1500,
                },
                {
                    "project": "Villa B",
                    "task": "Foundation",
                    "task_status": "Ongoing",
                    "material": "Cement",
                    "quantity": 200,
                    "unit": "kg",
                    "cost": 400,
                },
            ]
        )

        return {
            "sheets": [
                {
                    "name": "Project Materials",
                    "headers": ["Project", "Task", "Status", "Material", "Quantity", "Unit", "Cost"],
                    "field_names": ["project", "task", "task_status", "material", "quantity", "unit", "cost"],
                    "merge_rules": ["project", "task"],  # Merge when project/task repeat
                    "data": rows,
                }
            ]
        }


# ============================================================================
# Example 5: Grouped Headers
# ============================================================================


class EmployeeViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    """
    ViewSet with multi-level headers.

    Uses groups to create header categories.
    """

    queryset = None  # Employee.objects.all()
    serializer_class = None

    def get_export_data(self, request):
        """Export employee data with grouped headers."""
        queryset = self.filter_queryset(self.get_queryset())

        data = []
        for emp in queryset:
            data.append(
                {
                    "name": emp.full_name,
                    "email": emp.email,
                    "phone": emp.phone,
                    "department": emp.department.name,
                    "position": emp.position.name,
                    "salary": float(emp.salary),
                }
            )

        return {
            "sheets": [
                {
                    "name": "Employees",
                    "headers": ["Name", "Email", "Phone", "Department", "Position", "Salary"],
                    "field_names": ["name", "email", "phone", "department", "position", "salary"],
                    "groups": [
                        {"title": "Personal Information", "span": 3},
                        {"title": "Employment Details", "span": 3},
                    ],
                    "data": data,
                }
            ]
        }


# ============================================================================
# Example 6: Complex Report with Multiple Features
# ============================================================================


class ComplexReportViewSet(ExportXLSXMixin, viewsets.ViewSet):
    """
    Advanced export combining multiple features:
    - Multiple sheets
    - Grouped headers
    - Merged cells
    - Custom formatting
    """

    def get_export_data(self, request):
        """Generate comprehensive project report."""
        # Sheet 1: Executive Summary
        summary_data = [
            {"metric": "Total Projects", "value": "15", "change": "+3"},
            {"metric": "Active Projects", "value": "8", "change": "+2"},
            {"metric": "Completed Projects", "value": "7", "change": "+1"},
            {"metric": "Total Budget", "value": "$1,250,000", "change": "+15%"},
        ]

        # Sheet 2: Project Details with nested tasks
        project_details = []
        projects = [
            {
                "name": "Building A",
                "manager": "John Doe",
                "tasks": [
                    {"name": "Foundation", "progress": "100%", "hours": 160},
                    {"name": "Framing", "progress": "75%", "hours": 240},
                ],
            },
            {
                "name": "Villa B",
                "manager": "Jane Smith",
                "tasks": [
                    {"name": "Design", "progress": "100%", "hours": 80},
                    {"name": "Permits", "progress": "50%", "hours": 40},
                ],
            },
        ]

        # Flatten for export
        for project in projects:
            for task in project["tasks"]:
                project_details.append(
                    {
                        "project": project["name"],
                        "manager": project["manager"],
                        "task": task["name"],
                        "progress": task["progress"],
                        "hours": task["hours"],
                    }
                )

        return {
            "sheets": [
                {
                    "name": "Executive Summary",
                    "headers": ["Metric", "Current Value", "Change"],
                    "field_names": ["metric", "value", "change"],
                    "data": summary_data,
                },
                {
                    "name": "Project Details",
                    "headers": ["Project", "Manager", "Task Name", "Progress", "Hours"],
                    "field_names": ["project", "manager", "task", "progress", "hours"],
                    "groups": [
                        {"title": "Project Info", "span": 2},
                        {"title": "Task Info", "span": 3},
                    ],
                    "merge_rules": ["project", "manager"],
                    "data": project_details,
                },
            ]
        }


# ============================================================================
# Example 7: Export with Filters and Search
# ============================================================================


class FilteredExportViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    """
    ViewSet that respects filters and search when exporting.

    The export will only include filtered/searched results.
    """

    queryset = None  # Project.objects.all()
    serializer_class = None
    filterset_fields = ["status", "start_date", "manager"]
    search_fields = ["name", "description"]

    def get_export_data(self, request):
        """
        Export filtered queryset.

        The mixin automatically calls filter_queryset(), so the export
        includes only the filtered data that matches the query parameters.

        Example URLs:
            /api/projects/export/?status=active
            /api/projects/export/?search=building
            /api/projects/export/?manager=5&status=active
        """
        queryset = self.filter_queryset(self.get_queryset())

        data = []
        for project in queryset:
            data.append(
                {
                    "name": project.name,
                    "manager": project.manager.get_full_name(),
                    "status": project.get_status_display(),
                    "budget": float(project.budget),
                }
            )

        return {
            "sheets": [
                {
                    "name": f"Projects ({queryset.count()} items)",
                    "headers": ["Name", "Manager", "Status", "Budget"],
                    "field_names": ["name", "manager", "status", "budget"],
                    "data": data,
                }
            ]
        }


# ============================================================================
# Example 8: Direct Usage Without ViewSet
# ============================================================================


def generate_custom_report():
    """
    Use export components directly without a ViewSet.

    This is useful for:
    - Management commands
    - Background tasks
    - Admin-triggered reports
    - Scheduled exports
    """
    from libs.export_xlsx import XLSXGenerator, get_storage_backend

    # Define schema manually
    schema = {
        "sheets": [
            {
                "name": "Monthly Report",
                "headers": ["Month", "Revenue", "Expenses", "Profit"],
                "field_names": ["month", "revenue", "expenses", "profit"],
                "data": [
                    {"month": "January", "revenue": 100000, "expenses": 75000, "profit": 25000},
                    {"month": "February", "revenue": 120000, "expenses": 80000, "profit": 40000},
                    {"month": "March", "revenue": 110000, "expenses": 78000, "profit": 32000},
                ],
            }
        ]
    }

    # Generate XLSX
    generator = XLSXGenerator()
    file_content = generator.generate(schema)

    # Save to storage
    storage = get_storage_backend("s3")  # or 'local'
    file_path = storage.save(file_content, "monthly_report.xlsx")
    file_url = storage.get_url(file_path)

    return file_url


# ============================================================================
# Example 9: Async Export with Celery
# ============================================================================


class LargeDatasetViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    """
    ViewSet for exporting large datasets asynchronously.

    For datasets with >1000 rows, use async mode to avoid timeout.
    """

    queryset = None  # LargeModel.objects.all()
    serializer_class = None

    def get_export_data(self, request):
        """
        Export large dataset.

        Usage:
            GET /api/large-data/export/?async=true

        Response:
            {
                "task_id": "abc123",
                "status": "PENDING",
                "message": "Export started. Check status at ..."
            }

        Check status:
            GET /api/core/export/status/?task_id=abc123

        The file will be available when status is "SUCCESS".
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Process large dataset efficiently
        data = []
        for item in queryset.iterator(chunk_size=1000):  # Use iterator for large datasets
            data.append(
                {
                    "field1": item.field1,
                    "field2": item.field2,
                    # ... more fields
                }
            )

        return {
            "sheets": [
                {
                    "name": "Large Dataset",
                    "headers": ["Field 1", "Field 2"],
                    "field_names": ["field1", "field2"],
                    "data": data,
                }
            ]
        }


# ============================================================================
# Example 10: Auto-Schema with Custom Exclusions
# ============================================================================


class CustomAutoSchemaViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    """
    ViewSet using auto-schema but with custom field exclusions.
    """

    queryset = None  # MyModel.objects.all()
    serializer_class = None

    def get_export_data(self, request):
        """
        Use auto-schema but exclude additional sensitive fields.
        """
        from libs.export_xlsx import SchemaBuilder

        # Create builder with custom exclusions
        builder = SchemaBuilder(
            excluded_fields={
                "id",
                "created_at",
                "updated_at",
                "password_hash",  # Exclude sensitive field
                "internal_notes",  # Exclude internal field
            }
        )

        queryset = self.filter_queryset(self.get_queryset())
        model_class = self.queryset.model

        # Auto-generate schema with custom exclusions
        schema = builder.build_from_model(model_class, queryset)

        return schema
