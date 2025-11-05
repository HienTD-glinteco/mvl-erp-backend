# Import Template Download & Management

This document provides guidance on using the import template download and management features.

## Overview

The import template management system provides:

1. **Strict options validation** for import start requests
2. **Template download API** for retrieving per-app import templates
3. **Management command** for uploading template files to S3

## Import Options Validation

When starting an import job via `POST /.../import/`, the `options` parameter now undergoes strict validation.

### Allowed Options Keys

| Key | Type | Default | Range/Values | Description |
|-----|------|---------|--------------|-------------|
| `batch_size` | integer | 500 | 1-100000 | Number of rows to process per batch |
| `count_total_first` | boolean | true | true/false | Whether to count total rows before processing |
| `header_rows` | integer | 1 | 0-100 | Number of header rows to skip |
| `output_format` | string | "csv" | "csv", "xlsx" | Format for result files |
| `create_result_file_records` | boolean | true | true/false | Create FileModel records for results |
| `handler_path` | string\|null | null | - | Override handler path |
| `handler_options` | object | {} | - | Custom options for handler |
| `result_file_prefix` | string | - | - | Custom prefix for result files |

### Example Request

```bash
POST /api/employees/import/
{
  "file_id": 123,
  "options": {
    "batch_size": 1000,
    "count_total_first": true,
    "header_rows": 1,
    "output_format": "csv",
    "create_result_file_records": true,
    "handler_options": {
      "update_existing": true,
      "validate_references": true
    }
  }
}
```

### Validation Errors

If you provide an unknown key or invalid value, you'll receive a `400 Bad Request` with details:

```json
{
  "error": "Invalid option key: unknown_key. Allowed keys: batch_size, count_total_first, ..."
}
```

## Template Download API

ViewSets that use `AsyncImportProgressMixin` automatically get a `/import_template/` endpoint.

### Basic Usage

```python
from rest_framework.viewsets import ModelViewSet
from apps.imports.api.mixins import AsyncImportProgressMixin
from apps.hrm.models import Employee

class EmployeeViewSet(AsyncImportProgressMixin, ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
```

The template endpoint will be available at:

```
GET /api/employees/import_template/
```

### Response Format

```json
{
  "file_id": 456,
  "file_name": "hrm_employees_template.csv",
  "download_url": "https://s3.../template.csv?signature=...",
  "size": 1024,
  "created_at": "2025-11-05T10:30:00Z"
}
```

### Custom App Name

Override `get_import_template_app_name()` if you need custom app name resolution:

```python
class EmployeeViewSet(AsyncImportProgressMixin, ModelViewSet):
    queryset = Employee.objects.all()
    
    def get_import_template_app_name(self):
        # Custom logic to determine app name
        return "hrm"
```

## Uploading Templates

Use the `upload_import_templates` management command to upload template files.

### File Naming Convention

Templates must follow this naming pattern:

```
{app_name}_{resource}_template.{ext}
```

Examples:
- `hrm_employees_template.csv`
- `crm_customers_template.xlsx`
- `core_users_template.csv`

### Directory Structure

Organize your templates in a directory:

```
templates/
├── hrm_employees_template.csv
├── hrm_departments_template.xlsx
├── crm_customers_template.csv
└── core_users_template.csv
```

### Upload Command Usage

```bash
# Basic upload
python manage.py upload_import_templates /path/to/templates/

# With specific user
python manage.py upload_import_templates /path/to/templates/ --user-id 1

# With custom S3 prefix
python manage.py upload_import_templates /path/to/templates/ --s3-prefix "custom/templates/"

# Replace existing templates
python manage.py upload_import_templates /path/to/templates/ --replace

# Dry run (preview without uploading)
python manage.py upload_import_templates /path/to/templates/ --dry-run
```

### Command Options

- `directory` (required): Path to directory containing template files
- `--user-id`: ID of user to associate with uploaded files
- `--s3-prefix`: S3 prefix for template files (default: `templates/imports/`)
- `--replace`: Replace existing templates for the same app (archives old ones)
- `--dry-run`: Perform dry run without actually uploading

### Example Output

```
Found 3 template file(s):
  - hrm_employees_template.csv (app: hrm)
  - crm_customers_template.xlsx (app: crm)
  - core_users_template.csv (app: core)
  ✓ Uploaded: hrm_employees_template.csv (FileModel ID: 1)
  ✓ Uploaded: crm_customers_template.xlsx (FileModel ID: 2)
  ✓ Uploaded: core_users_template.csv (FileModel ID: 3)

============================================================
Successfully uploaded 3 template file(s)
============================================================
```

## Template Lookup Behavior

When a client requests a template via `/import_template/`:

1. System extracts the app name from the ViewSet's queryset model
2. Searches for `FileModel` records where:
   - `purpose` = `"import_template"`
   - `file_name` starts with the app name (case-insensitive)
   - `is_confirmed` = `True`
3. Returns the most recently created template

## Best Practices

1. **Template Naming**: Use descriptive names that clearly indicate the app and resource
2. **Version Control**: Keep template files in version control alongside your code
3. **Documentation**: Include column descriptions in template headers or comments
4. **Testing**: Test templates with sample data before deploying
5. **Updates**: Use `--replace` flag when updating templates to archive old versions
6. **Security**: Only authorized users should upload templates (use `--user-id` to track)

## Integration Example

Here's a complete example integrating all features:

```python
# apps/hrm/api/views.py
from rest_framework.viewsets import ModelViewSet
from apps.imports.api.mixins import AsyncImportProgressMixin
from apps.hrm.models import Employee
from apps.hrm.api.serializers import EmployeeSerializer

class EmployeeViewSet(AsyncImportProgressMixin, ModelViewSet):
    """Employee ViewSet with import capabilities."""
    
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    import_row_handler = "apps.hrm.import_handlers.employee_handler"
    
    # Optional: customize app name for template lookup
    def get_import_template_app_name(self):
        return "hrm"
```

Client usage:

```bash
# 1. Get the template
curl -X GET http://localhost:8000/api/employees/import_template/ \
  -H "Authorization: Bearer ${TOKEN}"

# Response: { "file_id": 123, "download_url": "...", ... }

# 2. Download template, fill it with data

# 3. Upload and confirm file
# (Use existing file upload flow)

# 4. Start import with validated options
curl -X POST http://localhost:8000/api/employees/import/ \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": 456,
    "options": {
      "batch_size": 1000,
      "header_rows": 1,
      "output_format": "csv"
    }
  }'
```

## Troubleshooting

### Template Not Found

If `/import_template/` returns 404:

1. Verify template file is uploaded with correct naming convention
2. Check that `is_confirmed` is `True` on the FileModel
3. Ensure app name matches (check `get_import_template_app_name()`)

### Invalid Options Error

If you get validation errors:

1. Check that all option keys are in the allowed list
2. Verify data types match the specification
3. Ensure values are within valid ranges

### Upload Command Fails

If `upload_import_templates` fails:

1. Verify directory path exists and contains template files
2. Check file naming convention: `{app}_{resource}_template.{ext}`
3. Ensure S3 credentials are configured correctly
4. Try `--dry-run` first to preview

## See Also

- [ASYNC_IMPORT_USAGE.md](./ASYNC_IMPORT_USAGE.md) - Async import usage guide
- [ASYNC_IMPORT_ARCHITECTURE.md](./ASYNC_IMPORT_ARCHITECTURE.md) - Import architecture overview
