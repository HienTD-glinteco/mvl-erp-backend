# XLSX Export Feature Guide

## Overview

The XLSX Export feature provides a reusable, schema-driven system for exporting data from Django REST Framework ViewSets to Excel files. It supports both synchronous and asynchronous (Celery-based) exports, with storage options for local filesystem or AWS S3.

## Quick Start

### 1. Basic Usage with ViewSet

Simply add `ExportXLSXMixin` to any ViewSet to enable XLSX export:

```python
from rest_framework import viewsets
from libs.export_xlsx import ExportXLSXMixin
from apps.core.models import Role
from apps.core.api.serializers import RoleSerializer

class RoleViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
```

This automatically adds a `/download/` action that exports the filtered queryset to XLSX format.

**API Endpoint:**
```
GET /api/roles/download/
```

The mixin will auto-generate the export schema from your model fields (excluding `id`, `created_at`, `updated_at`, etc.).

### 2. Custom Export Schema

Override `get_export_data()` to customize the export structure:

```python
class ProjectViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    
    def get_export_data(self, request):
        """Custom export with multiple sheets and grouped data."""
        queryset = self.filter_queryset(self.get_queryset())
        
        return {
            "sheets": [
                {
                    "name": "Projects Summary",
                    "headers": ["Name", "Start Date", "End Date", "Budget", "Status"],
                    "field_names": ["name", "start_date", "end_date", "budget", "status"],
                    "data": [
                        {
                            "name": project.name,
                            "start_date": project.start_date.isoformat(),
                            "end_date": project.end_date.isoformat(),
                            "budget": float(project.budget),
                            "status": project.get_status_display(),
                        }
                        for project in queryset
                    ],
                },
            ]
        }
```

### 3. Advanced: Nested Data with Merged Cells

For hierarchical data (e.g., Projects → Tasks → Materials):

```python
def get_export_data(self, request):
    """Export with nested structure and merged cells."""
    projects = self.filter_queryset(self.get_queryset())
    
    # Flatten nested data
    rows = []
    for project in projects:
        for task in project.tasks.all():
            for material in task.materials.all():
                rows.append({
                    "project_name": project.name,
                    "task_name": task.name,
                    "task_status": task.get_status_display(),
                    "material_name": material.name,
                    "quantity": material.quantity,
                    "unit": material.unit,
                    "cost": float(material.cost),
                })
    
    return {
        "sheets": [
            {
                "name": "Project Tasks & Materials",
                "headers": [
                    "Project", "Task Name", "Status",
                    "Material", "Quantity", "Unit", "Cost"
                ],
                "field_names": [
                    "project_name", "task_name", "task_status",
                    "material_name", "quantity", "unit", "cost"
                ],
                "groups": [
                    {"title": "Task Info", "span": 3},
                    {"title": "Material Details", "span": 4},
                ],
                "merge_rules": ["project_name", "task_name"],
                "data": rows,
            }
        ]
    }
```

**Result:** The `project_name` and `task_name` columns will be vertically merged when values repeat.

### 4. Grouped Headers

Create multi-level headers:

```python
{
    "sheets": [{
        "name": "Employee Data",
        "headers": ["Name", "Email", "Age", "Department", "Position", "Salary"],
        "groups": [
            {"title": "Personal Information", "span": 3},
            {"title": "Employment Details", "span": 3},
        ],
        "data": [...],
    }]
}
```

This creates a header row with grouped titles spanning multiple columns.

## Asynchronous Export

For large datasets, use async mode with Celery:

### Configuration

Add to your `.env` file:

```bash
EXPORTER_CELERY_ENABLED=true
EXPORTER_STORAGE_BACKEND=s3  # or 'local'
EXPORTER_S3_BUCKET_NAME=your-bucket-name
EXPORTER_S3_SIGNED_URL_EXPIRE=3600
EXPORTER_FILE_EXPIRE_DAYS=7
```

### API Usage

**1. Start async export:**
```
GET /api/projects/download/?async=true
```

**Response:**
```json
{
    "task_id": "abc123-def456-789",
    "status": "PENDING",
    "message": "Export started. Check status at /api/core/export/status/?task_id=abc123-def456-789"
}
```

**2. Check export status:**
```
GET /api/core/export/status/?task_id=abc123-def456-789
```

**Response (in progress):**
```json
{
    "task_id": "abc123-def456-789",
    "status": "PENDING"
}
```

**Response (completed):**
```json
{
    "task_id": "abc123-def456-789",
    "status": "SUCCESS",
    "file_url": "https://s3.amazonaws.com/bucket/exports/20250110_120000_projects_export.xlsx",
    "file_path": "exports/20250110_120000_projects_export.xlsx"
}
```

## Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `EXPORTER_CELERY_ENABLED` | `False` | Enable async export with Celery |
| `EXPORTER_STORAGE_BACKEND` | `local` | Storage backend: `local` or `s3` |
| `EXPORTER_S3_BUCKET_NAME` | `""` | S3 bucket name (uses `AWS_STORAGE_BUCKET_NAME` if not set) |
| `EXPORTER_S3_SIGNED_URL_EXPIRE` | `3600` | Signed URL expiration time (seconds) |
| `EXPORTER_FILE_EXPIRE_DAYS` | `7` | Auto-delete exported files after N days |
| `EXPORTER_LOCAL_STORAGE_PATH` | `exports` | Path for local storage (relative to `MEDIA_ROOT`) |

## Schema Reference

### Sheet Definition

```python
{
    "name": str,              # Sheet name
    "headers": [str, ...],    # Column headers
    "field_names": [str, ...],  # Field names (maps to data keys)
    "data": [dict, ...],      # Data rows
    "groups": [               # Optional: Grouped headers
        {
            "title": str,     # Group title
            "span": int,      # Number of columns to span
        }
    ],
    "merge_rules": [str, ...],  # Optional: Fields to merge vertically
}
```

### Default Auto-Generated Schema

When `get_export_data()` is not overridden, the system automatically:

1. Generates schema from model fields
2. Excludes: `id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `deleted_at`, `is_deleted`
3. Uses field `verbose_name` for headers
4. Serializes data using model field types
5. Filters data using ViewSet's `filter_queryset()` method

## Styling

The generator applies default styling:

- **Headers:** Bold, gray background (`#D3D3D3`), centered alignment
- **Data:** Bordered cells, left-aligned
- **Merged cells:** Centered alignment
- **Auto column width:** Adjusts to content (max 50 characters)

## Direct Usage (Without ViewSet)

You can use the components directly without a ViewSet:

```python
from libs.export_xlsx import XLSXGenerator, SchemaBuilder
from apps.core.models import Role

# Option 1: Auto-generate schema
builder = SchemaBuilder()
schema = builder.build_from_model(Role, queryset=Role.objects.all())

# Option 2: Manual schema
schema = {
    "sheets": [{
        "name": "Roles",
        "headers": ["Code", "Name"],
        "field_names": ["code", "name"],
        "data": [
            {"code": "admin", "name": "Administrator"},
            {"code": "user", "name": "User"},
        ],
    }]
}

# Generate XLSX
generator = XLSXGenerator()
file_content = generator.generate(schema)  # Returns BytesIO

# Save to file
with open("export.xlsx", "wb") as f:
    f.write(file_content.read())
```

## Celery Task

Use the export task directly in your code:

```python
from libs.export_xlsx import generate_xlsx_task

schema = {
    "sheets": [...]
}

# Trigger background task
task = generate_xlsx_task.delay(
    schema=schema,
    filename="custom_export.xlsx",
    storage_backend="s3"
)

print(f"Task ID: {task.id}")
```

## Storage Backends

### Local Storage

Files are saved to `MEDIA_ROOT/exports/` by default.

```python
from libs.export_xlsx import get_storage_backend

storage = get_storage_backend("local")
file_path = storage.save(file_content, "report.xlsx")
file_url = storage.get_url(file_path)
# file_url: "/media/exports/20250110_120000_report.xlsx"
```

### S3 Storage

Files are uploaded to AWS S3 with signed URLs.

```python
storage = get_storage_backend("s3")
file_path = storage.save(file_content, "report.xlsx")
file_url = storage.get_url(file_path)
# file_url: "https://bucket.s3.amazonaws.com/exports/20250110_120000_report.xlsx"
```

## Best Practices

1. **Use async mode for large datasets** (>1000 rows)
2. **Filter data in get_export_data()** to limit export size
3. **Use merge_rules sparingly** - they increase processing time
4. **Leverage auto-schema** for simple exports
5. **Override get_export_data()** for complex/custom exports
6. **Set appropriate S3_SIGNED_URL_EXPIRE** based on your security requirements
7. **Use grouped headers** to improve readability of wide exports

## Troubleshooting

### "Async export is not enabled" error
- Set `EXPORTER_CELERY_ENABLED=true` in settings
- Ensure Celery worker is running

### "Cannot determine model from queryset" error
- Ensure your ViewSet has a `queryset` attribute
- Check that `queryset.model` is accessible

### Files not uploading to S3
- Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set
- Check `AWS_STORAGE_BUCKET_NAME` or `EXPORTER_S3_BUCKET_NAME`
- Ensure S3 bucket has correct permissions

### Export is slow
- Use async mode: `?async=true`
- Reduce dataset size with filters
- Optimize queries (use `select_related`, `prefetch_related`)

## Example: Complete ViewSet

```python
from rest_framework import viewsets
from libs.export_xlsx import ExportXLSXMixin
from apps.project.models import Project
from apps.project.api.serializers import ProjectSerializer

class ProjectViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    """
    Project management ViewSet with XLSX export.
    
    Endpoints:
        GET /api/projects/ - List projects
        GET /api/projects/{id}/ - Retrieve project
        POST /api/projects/ - Create project
        PUT /api/projects/{id}/ - Update project
        DELETE /api/projects/{id}/ - Delete project
        GET /api/projects/download/ - Export to XLSX
        GET /api/projects/download/?async=true - Async export
    """
    
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filterset_fields = ["status", "start_date"]
    search_fields = ["name", "description"]
    
    def get_export_data(self, request):
        """Export projects with custom formatting."""
        queryset = self.filter_queryset(self.get_queryset())
        
        data = []
        for project in queryset.select_related("manager"):
            data.append({
                "name": project.name,
                "manager": project.manager.get_full_name() if project.manager else "",
                "start_date": project.start_date.isoformat(),
                "end_date": project.end_date.isoformat() if project.end_date else "",
                "budget": float(project.budget),
                "status": project.get_status_display(),
            })
        
        return {
            "sheets": [
                {
                    "name": "Projects",
                    "headers": ["Name", "Manager", "Start Date", "End Date", "Budget", "Status"],
                    "field_names": ["name", "manager", "start_date", "end_date", "budget", "status"],
                    "data": data,
                }
            ]
        }
```

## Future Enhancements

Potential improvements for future versions:

- [ ] Excel template support (use existing `.xlsx` as template)
- [ ] Data validation rules (dropdowns, number ranges)
- [ ] Cell formulas and calculations
- [ ] Conditional formatting
- [ ] Charts and graphs
- [ ] Password-protected exports
- [ ] Multiple export formats (CSV, PDF)
- [ ] Export history and caching
- [ ] Batch export (multiple files in ZIP)
- [ ] Scheduled/periodic exports
