# AsyncImportProgressMixin - Usage Guide

## Overview

The `AsyncImportProgressMixin` provides a reusable way to add asynchronous file import functionality to Django REST Framework ViewSets. It handles:

- Accepting confirmed file uploads
- Creating import jobs with progress tracking
- Processing files row-by-row using custom handlers
- Streaming large files to avoid memory issues
- Generating success and failure result files
- Real-time progress updates via Redis

## Quick Start

### 1. Define an Import Handler

Create a handler function that processes individual rows:

```python
# apps/myapp/import_handlers.py

def my_import_handler(row_index, row, import_job_id, options):
    """
    Process a single row from the import file.
    
    Args:
        row_index: 1-based row number
        row: List of cell values
        import_job_id: UUID of the import job
        options: Dict of import options
        
    Returns:
        {"ok": True, "result": {...}} on success
        {"ok": False, "error": "..."} on failure
    """
    try:
        # Parse row data
        name = row[0]
        email = row[1]
        
        # Validate
        if not email:
            return {"ok": False, "error": "Email is required"}
        
        # Process (create/update records)
        from apps.myapp.models import MyModel
        obj, created = MyModel.objects.update_or_create(
            email=email,
            defaults={'name': name}
        )
        
        return {"ok": True, "result": {"id": obj.id}}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

### 2. Add Mixin to ViewSet

```python
# apps/myapp/api/views.py

from rest_framework.viewsets import ModelViewSet
from apps.imports.api.mixins import AsyncImportProgressMixin
from apps.myapp.models import MyModel
from apps.myapp.api.serializers import MyModelSerializer


class MyModelViewSet(AsyncImportProgressMixin, ModelViewSet):
    """ViewSet with import capability."""
    
    queryset = MyModel.objects.all()
    serializer_class = MyModelSerializer
    
    # Specify the import handler
    import_row_handler = "apps.myapp.import_handlers.my_import_handler"
```

### 3. Use the Import API

#### Step 1: Upload and Confirm File

```bash
# Get presigned URL
POST /api/files/presign/
{
  "purpose": "employee_import",
  "file_name": "employees.csv"
}

# Upload file to presigned URL
PUT <presigned_url>
<file content>

# Confirm upload
POST /api/files/confirm/
{
  "files": [
    {
      "file_id": 123,
      "checksum": "abc123...",
      "size": 50000
    }
  ]
}
```

#### Step 2: Start Import

```bash
POST /api/mymodels/import/
{
  "file_id": 123,
  "options": {
    "batch_size": 500,
    "count_total_first": true,
    "header_rows": 1,
    "output_format": "csv",
    "create_result_file_records": true
  }
}

# Response (202 Accepted)
{
  "import_job_id": "a1b2c3d4-e5f6-...",
  "celery_task_id": "celery-task-...",
  "status": "queued",
  "created_at": "2025-10-22T10:30:00Z"
}
```

#### Step 3: Check Status

```bash
GET /api/import/status/?task_id=a1b2c3d4-e5f6-...

# Response
{
  "id": "a1b2c3d4-e5f6-...",
  "file_id": 123,
  "status": "running",
  "celery_task_id": "celery-task-...",
  "created_by_id": 5,
  "created_at": "2025-10-22T10:30:00Z",
  "started_at": "2025-10-22T10:30:05Z",
  "finished_at": null,
  "total_rows": 10000,
  "processed_rows": 2500,
  "success_count": 2480,
  "failure_count": 20,
  "percentage": 25.0,
  "result_files": {
    "success_file": {
      "file_id": null,
      "url": null
    },
    "failed_file": {
      "file_id": null,
      "url": null
    }
  },
  "error_message": null
}
```

#### Step 4: Download Results

When `status` is `"succeeded"`, download result files:

```bash
GET /api/import/status/?task_id=a1b2c3d4-e5f6-...

# Response
{
  "status": "succeeded",
  "processed_rows": 10000,
  "success_count": 9950,
  "failure_count": 50,
  "result_files": {
    "success_file": {
      "file_id": 456,
      "url": "https://s3.../success_file.csv?signature=..."
    },
    "failed_file": {
      "file_id": 457,
      "url": "https://s3.../failed_file.csv?signature=..."
    }
  }
}
```

## Configuration Options

### Import Options (request body)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `batch_size` | int | 500 | Rows to process before updating progress |
| `count_total_first` | bool | true | Count total rows before processing (slower but provides progress %) |
| `header_rows` | int | 1 | Number of header rows to skip |
| `output_format` | string | "csv" | Format for result files ("csv" or "xlsx") |
| `create_result_file_records` | bool | true | Create FileModel records for results |
| `handler_path` | string | - | Override class-level handler path |

### Django Settings

Add to `settings/base/imports.py`:

```python
# Import batch size for progress updates
IMPORT_DEFAULT_BATCH_SIZE = 500

# Flush progress to DB every N batches
IMPORT_PROGRESS_DB_FLUSH_EVERY_N_BATCHES = 5

# Temporary directory for result files
IMPORT_TEMP_DIR = None  # None = system temp

# Presigned URL expiration for result files
IMPORT_RESULT_PRESIGN_EXPIRES = 3600  # 1 hour

# S3 prefix for result files
IMPORT_S3_PREFIX = "uploads/imports/"

# Enable result file creation
IMPORT_ENABLE_RESULT_FILES = True
```

## Advanced Usage

### Dynamic Handler Selection

Override `get_import_handler_path()` for dynamic handler selection:

```python
class MyModelViewSet(AsyncImportProgressMixin, ModelViewSet):
    def get_import_handler_path(self):
        # Select handler based on user role or other criteria
        if self.request.user.is_staff:
            return "apps.myapp.handlers.admin_import_handler"
        return "apps.myapp.handlers.user_import_handler"
```

### Custom Options in Handler

Pass custom options to your handler:

```python
# API request
POST /api/mymodels/import/
{
  "file_id": 123,
  "options": {
    "update_existing": true,
    "validate_references": true,
    "custom_field": "value"
  }
}

# Handler function
def my_handler(row_index, row, import_job_id, options):
    update_existing = options.get('update_existing', False)
    validate_refs = options.get('validate_references', False)
    # Use options in processing logic
```

### Cancellation

Cancel a running import:

```python
# In your ViewSet, add the cancel mixin
from apps.imports.api.mixins import AsyncImportCancelMixin

class MyModelViewSet(AsyncImportProgressMixin, AsyncImportCancelMixin, ModelViewSet):
    pass

# API call
POST /api/imports/{job_id}/cancel/
```

### Accessing Result Files

Failed rows include the original data plus an `import_error` column:

```csv
col_0,col_1,col_2,import_error
John,Doe,invalid-email,Email is required
Jane,,jane@example.com,First name and last name are required
```

## Handler Best Practices

### 1. Return Consistent Format

Always return `{"ok": bool, ...}`:

```python
# Good
return {"ok": True, "result": {"id": 123}}
return {"ok": False, "error": "Validation failed"}

# Bad
return True  # Not a dict
return {"success": True}  # Wrong key
```

### 2. Handle Exceptions

Catch exceptions to prevent task failure:

```python
def my_handler(row_index, row, import_job_id, options):
    try:
        # Processing logic
        return {"ok": True, "result": {...}}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

### 3. Validate Input

Validate row data before processing:

```python
def my_handler(row_index, row, import_job_id, options):
    # Check row length
    if len(row) < 3:
        return {"ok": False, "error": "Row has insufficient columns"}
    
    # Validate data
    email = row[2]
    if not email or '@' not in email:
        return {"ok": False, "error": "Invalid email format"}
    
    # Process...
```

### 4. Use Bulk Operations

For performance, consider batching database operations:

```python
# Global cache for batch operations
_batch_cache = []

def my_handler(row_index, row, import_job_id, options):
    global _batch_cache
    
    # Add to batch
    _batch_cache.append({
        'email': row[0],
        'name': row[1]
    })
    
    # Flush batch periodically
    batch_size = options.get('batch_size', 500)
    if len(_batch_cache) >= batch_size:
        MyModel.objects.bulk_create([
            MyModel(**data) for data in _batch_cache
        ])
        _batch_cache.clear()
    
    return {"ok": True, "result": {"cached": True}}
```

### 5. Log Important Events

Use the import_job_id for debugging:

```python
import logging

logger = logging.getLogger(__name__)

def my_handler(row_index, row, import_job_id, options):
    logger.info(f"Processing row {row_index} for job {import_job_id}")
    # ...
```

## Testing

Example test for import functionality:

```python
import pytest
from django.core.files.base import ContentFile
from apps.files.models import FileModel
from apps.imports.models import ImportJob


@pytest.mark.django_db
def test_import_creates_job(api_client, authenticated_user):
    # Create a test file
    file_obj = FileModel.objects.create(
        purpose="test_import",
        file_name="test.csv",
        file_path="test/test.csv",
        is_confirmed=True,
        uploaded_by=authenticated_user
    )
    
    # Start import
    response = api_client.post('/api/mymodels/import/', {
        'file_id': file_obj.id,
        'options': {'batch_size': 100}
    })
    
    assert response.status_code == 202
    assert 'import_job_id' in response.data
    
    # Check job was created
    job = ImportJob.objects.get(id=response.data['import_job_id'])
    assert job.status == 'queued'
    assert job.file == file_obj
```

## Troubleshooting

### Import job fails immediately

Check:
- Handler path is correct and importable
- File exists and is confirmed
- Database connectivity

### Progress not updating

Check:
- Redis is running and accessible
- `IMPORT_PROGRESS_DB_FLUSH_EVERY_N_BATCHES` setting
- Celery worker is running

### Out of memory errors

Reduce `batch_size` or disable `count_total_first`:

```python
{
  "options": {
    "batch_size": 100,
    "count_total_first": false
  }
}
```

### Result files not created

Check:
- `IMPORT_ENABLE_RESULT_FILES` is True
- S3 credentials are valid
- `IMPORT_S3_PREFIX` is correct

## See Also

- [IMPORT_HANDLER_EXAMPLE.py](./IMPORT_HANDLER_EXAMPLE.py) - Example handlers
- SRS Document - Full technical specification
- ExportXLSXMixin - Similar pattern for exports
