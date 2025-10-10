# Import Feature Enhancements - Implementation Guide

## Overview

This document describes the 4 major enhancements added to the XLSX import feature based on user feedback.

## 1. Async Import with Celery

### Problem
Large files (>1000 rows) can cause timeout issues with synchronous processing.

### Solution
Background processing using Celery workers, similar to the export feature.

### Configuration

Add to `.env`:
```bash
IMPORTER_CELERY_ENABLED=true
IMPORTER_STORAGE_BACKEND=local  # or 's3'
IMPORTER_S3_BUCKET_NAME=your-bucket  # if using S3
IMPORTER_S3_SIGNED_URL_EXPIRE=3600
```

### Usage

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@large_file.xlsx" \
  "http://localhost:8000/api/roles/import/?async=true"
```

**Response (202 Accepted):**
```json
{
  "task_id": "abc-123-def-456",
  "status": "PENDING",
  "message": "Import task has been queued for processing"
}
```

**Check Task Status:**
```python
from celery.result import AsyncResult

task = AsyncResult('abc-123-def-456')
print(task.status)  # PENDING, PROCESSING, SUCCESS, FAILED
print(task.result)  # Task result when complete
```

### Implementation Details

- **File:** `libs/import_xlsx/tasks.py`
- **Task:** `import_xlsx_task`
- **Storage:** Temporary files saved to storage backend
- **Cleanup:** Files auto-deleted after processing

---

## 2. Preview/Dry-Run Mode

### Problem
Users want to validate data without committing changes to database.

### Solution
Add `?preview=true` parameter to validate and show results without saving.

### Usage

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@data.xlsx" \
  "http://localhost:8000/api/roles/import/?preview=true"
```

**Response (200 OK):**
```json
{
  "valid_count": 95,
  "invalid_count": 5,
  "errors": [
    {
      "row": 3,
      "errors": {
        "email": ["Enter a valid email address."]
      }
    },
    {
      "row": 7,
      "errors": {
        "code": ["This field is required"]
      }
    }
  ],
  "preview_data": [
    {
      "name": "Role A",
      "code": "ROLE_A",
      "description": "Description"
    },
    {
      "name": "Role B",
      "code": "ROLE_B",
      "description": "Another description"
    }
  ],
  "detail": "Preview completed successfully"
}
```

### Features

- Shows first 10 valid rows that would be imported
- Lists all validation errors
- No database changes
- Fast response (no saving overhead)

### Use Cases

1. **Testing Import Configuration**
   - Verify field mapping is correct
   - Check data format compliance

2. **User Validation**
   - Allow users to check before committing
   - Catch errors early

3. **Development/QA**
   - Test import logic without side effects
   - Quick iteration on import schemas

---

## 3. Error Report Download

### Problem
When imports fail, users need detailed error information to fix data.

### Solution
Auto-generate downloadable XLSX error report with highlighted errors.

### Automatic Generation

When import completes with errors, response includes `error_file_url`:

```json
{
  "success_count": 95,
  "error_count": 5,
  "errors": [
    {
      "row": 3,
      "errors": {"email": ["Invalid format"]}
    }
  ],
  "error_file_url": "https://s3.amazonaws.com/bucket/imports/errors/import_errors_20240110_153045.xlsx",
  "detail": "Import completed successfully"
}
```

### Error Report Format

The generated XLSX file contains two sheets:

#### Sheet 1: Error Summary
| Row Number | Field | Error Message |
|------------|-------|---------------|
| 3          | email | Enter a valid email address |
| 5          | code  | This field is required |
| 7          | name  | This field must be unique |

#### Sheet 2: Original Data with Errors
| name | code | email | **Error** |
|------|------|-------|-----------|
| John | ADM  | john@example.com | |
| Jane | MGR  | invalid | **email: Enter a valid email address** |
| Bob  |      | bob@example.com | **code: This field is required** |

**Features:**
- Error rows highlighted in red
- Professional formatting
- Easy to share with users
- Contains all necessary context

### Implementation

**File:** `libs/import_xlsx/error_report.py`
**Class:** `ErrorReportGenerator`

---

## 4. Relational Fields Support

### Problem
Importing data with ForeignKey and ManyToMany relationships is complex.

### Solution
Automatic resolution of related objects by ID, natural keys, or display names.

### ForeignKey Support

**Multiple Resolution Methods:**

Excel file can reference related objects in multiple ways:

```
| name      | department  |
|-----------|-------------|
| Project A | 5           |  ← By primary key (ID)
| Project B | Engineering |  ← By name
| Project C | ENG         |  ← By code
| Project D | eng@co.com  |  ← By email
```

**Resolution Logic:**
1. Try primary key (if numeric)
2. Try natural keys: `name`, `code`, `email`, `username`
3. Case-insensitive matching
4. Error if not found

### ManyToMany Support

**Comma-Separated Values:**

```
| name        | code  | permissions           |
|-------------|-------|-----------------------|
| Admin       | ADMIN | 1,2,3,4              |  ← By IDs
| Manager     | MGR   | view,edit,delete     |  ← By names
| Basic User  | USER  | view                 |  ← Single value
| Power User  | POWER | 5,edit,view,create   |  ← Mixed
```

**Features:**
- Comma-separated values
- Mix IDs and names
- Automatic resolution
- Empty/null handling

### Code Example

**Model:**
```python
class Project(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag, blank=True)
```

**Excel File:**
```
| name      | department  | tags        |
|-----------|-------------|-------------|
| Project A | Engineering | urgent,new  |
| Project B | 5           | 1,2,3       |
```

**Import:**
```bash
POST /api/projects/import/
# Automatically resolves:
# - department by name or ID
# - tags by name or ID
```

### Error Handling

If related object not found:

```json
{
  "row": 5,
  "errors": {
    "department": "Related object not found for department: InvalidDept"
  }
}
```

### Custom Resolution

Override for specific needs:

```python
class ProjectViewSet(ImportXLSXMixin, BaseModelViewSet):
    def get_import_schema(self, request, file):
        schema = super().get_import_schema(request, file)
        
        # Add custom resolvers
        schema["resolvers"] = {
            "department": lambda value: Department.objects.get(
                Q(code=value) | Q(name__iexact=value)
            )
        }
        
        return schema
```

---

## Configuration Summary

### Environment Variables

```bash
# Async Import
IMPORTER_CELERY_ENABLED=false
IMPORTER_STORAGE_BACKEND=local
IMPORTER_LOCAL_STORAGE_PATH=imports
IMPORTER_FILE_EXPIRE_DAYS=7

# S3 Storage (if using)
IMPORTER_S3_BUCKET_NAME=
IMPORTER_S3_SIGNED_URL_EXPIRE=3600

# Preview
IMPORTER_MAX_PREVIEW_ROWS=10
```

### Settings File

**Location:** `settings/base/import_xlsx.py`

```python
IMPORTER_CELERY_ENABLED = config("IMPORTER_CELERY_ENABLED", default=False, cast=bool)
IMPORTER_STORAGE_BACKEND = config("IMPORTER_STORAGE_BACKEND", default="local")
IMPORTER_LOCAL_STORAGE_PATH = "imports"
IMPORTER_MAX_PREVIEW_ROWS = config("IMPORTER_MAX_PREVIEW_ROWS", default=10, cast=int)
```

---

## API Parameter Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `async` | boolean | false | Process import in background with Celery |
| `preview` | boolean | false | Validate without saving (dry-run) |

**Examples:**

```bash
# Sync import (default)
POST /api/roles/import/

# Async import
POST /api/roles/import/?async=true

# Preview mode
POST /api/roles/import/?preview=true

# Async preview (validates in background)
POST /api/roles/import/?async=true&preview=true
```

---

## Response Types

### Sync Import (200 OK)

```json
{
  "success_count": 95,
  "error_count": 5,
  "errors": [...],
  "error_file_url": "https://...",
  "detail": "Import completed successfully"
}
```

### Async Import (202 Accepted)

```json
{
  "task_id": "abc-123",
  "status": "PENDING",
  "message": "Import task has been queued"
}
```

### Preview (200 OK)

```json
{
  "valid_count": 95,
  "invalid_count": 5,
  "errors": [...],
  "preview_data": [...],
  "detail": "Preview completed successfully"
}
```

---

## Backward Compatibility

✅ All new features are **opt-in** via query parameters

✅ Default behavior unchanged (sync import)

✅ Existing code continues to work without modifications

✅ Relational field resolution is automatic and backward compatible

---

## Testing

### Unit Tests

Test files created in `tests/libs/test_import_xlsx_*`:

- `test_async_import.py` - Async processing tests
- `test_preview_mode.py` - Preview validation tests
- `test_error_reports.py` - Error report generation tests
- `test_relational_fields.py` - ForeignKey/M2M resolution tests

### Manual Testing

```bash
# 1. Test async import
poetry run celery -A celery_tasks worker -l info
curl -X POST -F "file=@large.xlsx" "http://localhost:8000/api/roles/import/?async=true"

# 2. Test preview
curl -X POST -F "file=@test.xlsx" "http://localhost:8000/api/roles/import/?preview=true"

# 3. Test error report (use file with errors)
curl -X POST -F "file=@errors.xlsx" "http://localhost:8000/api/roles/import/"
# Check error_file_url in response

# 4. Test relational fields
# Create XLSX with ForeignKey/M2M references
curl -X POST -F "file=@relational.xlsx" "http://localhost:8000/api/projects/import/"
```

---

## Performance Considerations

### Async Import
- **Threshold:** Use async for files >1000 rows
- **Worker Scaling:** Scale Celery workers based on load
- **Memory:** Monitor Redis/RabbitMQ memory usage

### Error Reports
- **Storage:** Large error reports stored in S3/local storage
- **Expiration:** Auto-cleanup after 7 days (configurable)
- **Size Limit:** Report includes up to 10,000 errors

### Relational Resolution
- **Caching:** Consider caching related object lookups
- **Bulk Queries:** Uses select_related/prefetch_related internally
- **N+1 Prevention:** Optimized query patterns

---

## Troubleshooting

### Async Import Not Working

**Check:**
1. `IMPORTER_CELERY_ENABLED=true` in settings
2. Celery worker is running
3. Redis/RabbitMQ is accessible

**Debug:**
```bash
poetry run celery -A celery_tasks worker -l debug
```

### Error Reports Not Generated

**Check:**
1. Storage backend configured correctly
2. Permissions for file writing
3. S3 credentials (if using S3)

### Relational Fields Not Resolving

**Check:**
1. Related objects exist in database
2. Field names match (case-insensitive)
3. No typos in Excel data

**Debug:**
Enable debug logging:
```python
import logging
logging.getLogger('libs.import_xlsx').setLevel(logging.DEBUG)
```

---

## Future Enhancements

Potential additions:
- [ ] Progress tracking for async imports
- [ ] Webhook notifications on completion
- [ ] Batch async import (multiple files)
- [ ] Custom field transformers
- [ ] Import templates download
- [ ] Historical import logs

---

## Summary

All 4 requested features have been successfully implemented:

1. ✅ **Async Import** - Background processing for large files
2. ✅ **Preview Mode** - Validate without saving
3. ✅ **Error Reports** - Downloadable XLSX with errors
4. ✅ **Relational Support** - ForeignKey and ManyToMany auto-resolution

The implementation is production-ready, well-documented, and maintains backward compatibility.
