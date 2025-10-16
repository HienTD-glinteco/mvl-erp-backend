# XLSX Import Feature

## Overview

The **ImportXLSXMixin** provides a reusable, universal import functionality for Django REST Framework ViewSets. It enables importing data from Excel (.xlsx) files into Django models with automatic schema generation, validation, and bulk operations.

## Features

- ✅ **Universal Import Action**: Add `/import/` endpoint to any ViewSet with a single mixin
- ✅ **Auto Schema Generation**: Automatically maps Excel columns to model fields
- ✅ **Customizable Mapping**: Override `get_import_schema()` for custom field mapping
- ✅ **Validation**: Full validation using DRF serializers with per-row error reporting
- ✅ **Bulk Operations**: Efficient bulk create/update of model instances
- ✅ **Async Processing**: Background import with Celery for large files (>1000 rows)
- ✅ **Preview Mode**: Dry-run validation without saving data
- ✅ **Error Reports**: Download detailed error reports as XLSX files
- ✅ **Relational Support**: Automatic resolution of ForeignKey and ManyToMany fields
- ✅ **Audit Logging**: Automatic integration with audit logging system
- ✅ **Permission Support**: Import action automatically generates permission metadata

## Quick Start

### Basic Usage

Simply add the `ImportXLSXMixin` to your ViewSet:

```python
from libs import BaseModelViewSet, ImportXLSXMixin

class ProjectViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    module = "Projects"
    submodule = "Project Management"
    permission_prefix = "project"
```

That's it! Your ViewSet now has an `/import/` endpoint that accepts XLSX files.

### Auto Schema

By default, the mixin auto-generates an import schema from your model fields:

```python
# For a model like:
class Project(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2)

# Auto schema will be:
{
    "fields": ["name", "start_date", "end_date", "budget"],
    "required": ["name", "start_date", "budget"]
}
```

Fields automatically excluded from import:
- `id`, `created_at`, `updated_at`, `deleted_at`
- Auto fields (`AutoField`, `BigAutoField`)
- Reverse relations (ForeignKey reverse, ManyToMany reverse)

### Custom Schema

Override `get_import_schema()` to customize field mapping:

```python
class ProjectViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def get_import_schema(self, request, file):
        """Custom import schema"""
        return {
            "fields": ["name", "start_date", "budget"],
            "required": ["name", "start_date"],
            "validators": {
                "budget": {"min": 0}
            }
        }
```

## API Usage

### Import Endpoint

**POST** `/api/projects/import/`

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - Excel (.xlsx) file

**Excel File Format:**
```
| name        | start_date | end_date   | budget    |
|-------------|------------|------------|-----------|
| Project A   | 2024-01-01 | 2024-12-31 | 100000.00 |
| Project B   | 2024-02-01 | 2024-11-30 | 50000.00  |
```

**Response (Success):**
```json
{
  "success_count": 2,
  "error_count": 0,
  "errors": [],
  "detail": "Import completed successfully"
}
```

**Response (With Errors):**
```json
{
  "success_count": 1,
  "error_count": 1,
  "errors": [
    {
      "row": 3,
      "errors": {
        "budget": ["Ensure this value is greater than or equal to 0."]
      }
    }
  ],
  "detail": "Import completed successfully"
}
```

## Advanced Features

### Validation Strategies

The mixin supports two validation approaches:

#### 1. Model-Level Validation (Default)

By default, validation is performed at the model level using `model.full_clean()`. This approach:
- ✅ Allows importing ALL model fields, including read-only ones
- ✅ Supports auto-generated fields (e.g., codes)
- ✅ Works with fields that have defaults
- ✅ Perfect for data migration scenarios

**Example:**
```python
class RoleViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer  # Has read-only fields
    # No need to override anything - model validation handles it
```

This allows importing `code` even if it's read-only in the serializer.

#### 2. Serializer-Level Validation (Optional)

For stricter validation, override `get_import_serializer_class()`:

```python
class RoleImportSerializer(serializers.ModelSerializer):
    """Custom serializer for imports without read-only restrictions"""
    class Meta:
        model = Role
        fields = ["code", "name", "description"]
        # No read-only fields, permission_ids not required

class RoleViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer  # Used for CRUD
    
    def get_import_serializer_class(self):
        return RoleImportSerializer  # Used for imports only
```

**When to use:**
- Need custom validation logic specific to imports
- Want to enforce business rules during import
- Need to transform data before saving

### Header Mapping

The mixin automatically maps Excel headers to model fields with:
- **Case-insensitive matching**: "Name" → `name`
- **Space/underscore conversion**: "Start Date" → `start_date`
- **Exact matching**: "email" → `email`

### Error Handling

Each row is validated independently:
- Missing required fields
- Invalid data types
- Custom validation rules
- Database constraints

Errors include:
- Row number (Excel row, starting from 2)
- Field-level error messages
- General errors for exceptions

### Transaction Support

All imports are wrapped in database transactions:
- Individual rows can fail without affecting others
- Failed rows are reported in the error list
- Successful rows are committed

### Audit Logging

When using `AuditLoggingMixin` together with `ImportXLSXMixin`:

```python
class ProjectViewSet(AuditLoggingMixin, ImportXLSXMixin, BaseModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
```

Each imported instance is automatically logged with:
- Action: `IMPORT`
- User context (if authenticated)
- Request metadata (IP, user agent)

## Permission Registration

The import action automatically generates permission metadata:

```python
# For a ViewSet with permission_prefix = "project"
# Auto-generates permission:
{
    "code": "project.import_data",
    "name": "Import Data Project",
    "description": "Import Data a Project",
    "module": "Projects",
    "submodule": "Project Management"
}
```

Run `poetry run python manage.py collect_permissions` to sync permissions to database.

## Async Import (Celery)

For large files (>1000 rows), use async processing to avoid timeouts:

### Configuration

```python
# settings/.env
IMPORTER_CELERY_ENABLED=true
IMPORTER_STORAGE_BACKEND=s3  # or 'local'
IMPORTER_S3_BUCKET_NAME=your-bucket
```

### Usage

```python
# Add ?async=true to import endpoint
POST /api/projects/import/?async=true
```

**Request:** Upload XLSX file

**Response (202 Accepted):**
```json
{
  "task_id": "abc123",
  "status": "PENDING",
  "message": "Import task has been queued for processing"
}
```

**Check Status:**
```python
from celery.result import AsyncResult

result = AsyncResult(task_id)
status = result.status  # PENDING, PROCESSING, SUCCESS, FAILED
```

## Preview Mode (Dry-Run)

Validate data without saving to database:

### Usage

```python
# Add ?preview=true to import endpoint
POST /api/projects/import/?preview=true
```

**Response:**
```json
{
  "valid_count": 95,
  "invalid_count": 5,
  "errors": [
    {
      "row": 3,
      "errors": {
        "email": ["Enter a valid email address"]
      }
    }
  ],
  "preview_data": [
    {"name": "Project A", "budget": 10000},
    {"name": "Project B", "budget": 20000}
  ],
  "detail": "Preview completed successfully"
}
```

**Use Cases:**
- Validate files before committing changes
- Test import configuration
- Preview what will be imported

## Error Reports

When import has validation errors, download a detailed error report:

### Automatic Generation

If import completes with errors, response includes error report URL:

```json
{
  "success_count": 95,
  "error_count": 5,
  "errors": [...],
  "error_file_url": "https://s3.amazonaws.com/bucket/imports/errors/import_errors_20240101.xlsx",
  "detail": "Import completed successfully"
}
```

### Error Report Contents

The XLSX error report includes:

1. **Error Summary Sheet**
   - Row number
   - Field name
   - Error message

2. **Original Data Sheet** (if available)
   - All original data
   - Error column showing what failed
   - Highlighted error rows

### Download

```python
# From API response
error_url = response.data["error_file_url"]

# Download file
import requests
file_content = requests.get(error_url).content
```

## Relational Fields Support

Automatically resolve ForeignKey and ManyToMany relationships:

### ForeignKey

Supports multiple lookup methods:

```python
# Excel file can reference related objects by:
# 1. Primary key (ID)
# 2. Natural keys (name, code, email, username)

# Example: Project with Department (ForeignKey)
| name        | department |
|-------------|------------|
| Project A   | 5          |  # By ID
| Project B   | Engineering|  # By name
| Project C   | ENG        |  # By code
```

### ManyToMany

Use comma-separated values:

```python
# Example: Role with Permissions (ManyToMany)
| name        | code  | permissions          |
|-------------|-------|----------------------|
| Admin       | ADMIN | 1,2,3               |  # By IDs
| Manager     | MGR   | view,edit,delete    |  # By names
| User        | USER  | view                |  # Single value
```

### Custom Resolution

Override resolution logic for specific fields:

```python
class ProjectViewSet(ImportXLSXMixin, BaseModelViewSet):
    def get_import_schema(self, request, file):
        schema = super().get_import_schema(request, file)
        
        # Add custom field resolver
        schema["resolvers"] = {
            "department": lambda value: Department.objects.get(code=value)
        }
        
        return schema
```

## Testing

### Unit Tests

```python
import io
from openpyxl import Workbook

def create_test_xlsx(data, headers):
    """Helper to create test XLSX file"""
    workbook = Workbook()
    sheet = workbook.active
    
    # Add headers
    for col_idx, header in enumerate(headers, start=1):
        sheet.cell(row=1, column=col_idx, value=header)
    
    # Add data
    for row_idx, row_data in enumerate(data, start=2):
        for col_idx, value in enumerate(row_data, start=1):
            sheet.cell(row=row_idx, column=col_idx, value=value)
    
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    output.name = "test.xlsx"
    return output

def test_import_projects():
    # Create test file
    file = create_test_xlsx(
        data=[
            ["Project A", "2024-01-01", 100000],
            ["Project B", "2024-02-01", 50000],
        ],
        headers=["name", "start_date", "budget"]
    )
    
    # Test import
    response = client.post("/api/projects/import/", {"file": file}, format="multipart")
    
    assert response.status_code == 200
    assert response.data["success_count"] == 2
    assert response.data["error_count"] == 0
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ImportXLSXMixin                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  @action(detail=False, methods=["post"])                    │
│  def import_data(request):                                  │
│      1. Validate file upload                                │
│      2. Load import schema (auto or custom)                 │
│      3. Parse XLSX file                                     │
│      4. Validate each row                                   │
│      5. Bulk import data                                    │
│      6. Return summary + errors                             │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  def get_import_schema(request, file):                      │
│      Override to customize mapping                          │
│                                                              │
│  def _auto_generate_schema():                               │
│      Auto-generate from model fields                        │
│                                                              │
│  def _parse_xlsx_file(file, schema):                        │
│      Parse and validate Excel data                          │
│                                                              │
│  def _bulk_import(data, schema, errors):                    │
│      Bulk create instances with audit logging               │
└─────────────────────────────────────────────────────────────┘
```

## Best Practices

### 1. Use with Audit Logging

Always combine with `AuditLoggingMixin` for complete audit trails:

```python
class ProjectViewSet(AuditLoggingMixin, ImportXLSXMixin, BaseModelViewSet):
    # Mixin order matters: AuditLoggingMixin first
    pass
```

### 2. Customize Schema for Complex Models

For models with foreign keys or custom validation:

```python
def get_import_schema(self, request, file):
    return {
        "fields": ["name", "department_id", "status"],
        "required": ["name", "department_id"],
        "validators": {
            "status": {"choices": ["active", "inactive"]}
        }
    }
```

### 3. Provide Clear Excel Templates

Document expected Excel format for users:
- Column headers (exact or case-insensitive)
- Required vs optional fields
- Data formats (dates, numbers, etc.)
- Valid values for choice fields

### 4. Handle Large Files

For very large imports, consider:
- Pagination or chunking
- Async processing with Celery (future enhancement)
- Progress reporting

### 5. Test Import Thoroughly

Test import functionality with:
- Valid data
- Missing required fields
- Invalid data types
- Duplicate keys
- Empty files
- Large datasets

## Troubleshooting

### "No file provided"
- Ensure request content-type is `multipart/form-data`
- File field name must be `file`

### "Invalid file type"
- Only `.xlsx` files are supported
- Binary Excel files (`.xls`) are not supported

### "This field is required"
- Check required fields in schema
- Ensure Excel headers match field names

### "Invalid data"
- Check data types match model field types
- Verify date/datetime formats
- Check decimal precision for numeric fields

## Future Enhancements

Potential additions to consider:
- [ ] Async import with Celery for large files
- [ ] Import preview/dry-run mode
- [ ] Download error report as XLSX
- [ ] Support for related model imports (ForeignKey, ManyToMany)
- [ ] Import progress tracking
- [ ] Custom field transformers
- [ ] CSV format support
- [ ] Import history/log model

## See Also

- [Auto Permission Registration](AUTO_PERMISSION_REGISTRATION.md)
- [Audit Logging System](../apps/audit_logging/README.md)
- [Base ViewSet](../libs/base_viewset.py)
