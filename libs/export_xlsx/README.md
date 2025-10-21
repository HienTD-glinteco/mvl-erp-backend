# XLSX Export Module

Dynamic XLSX exporter for Django REST Framework with support for async processing, progress tracking, and multiple storage backends.

## Features

- ✅ **Auto-schema generation** from Django models
- ✅ **Custom export schemas** with full control
- ✅ **Nested data support** with automatic flattening
- ✅ **Merged cells** for grouped data visualization
- ✅ **Multi-level headers** with grouping
- ✅ **Async export** via Celery (optional)
- ✅ **Real-time progress tracking** with percentage, speed, and ETA
- ✅ **Multiple storage backends** (Local, S3)
- ✅ **Automatic styling** with sensible defaults
- ✅ **ViewSet mixin** for zero-config exports

## Installation

The module is included in the `libs/export_xlsx` package. Dependencies:

- `openpyxl` - Excel file generation
- `celery` - Async task processing (optional)
- `django-storages` - S3 storage (optional)

## Quick Start

### 1. Add to ViewSet

```python
from rest_framework import viewsets
from libs.export_xlsx import ExportXLSXMixin

class MyViewSet(ExportXLSXMixin, viewsets.ModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MySerializer
```

### 2. Use the API

```bash
# Synchronous export
GET /api/my-endpoint/export/

# Asynchronous export (requires Celery)
GET /api/my-endpoint/export/?async=true
```

## Module Structure

```
libs/export_xlsx/
├── __init__.py          # Public API exports
├── constants.py         # Constants and error messages
├── schema_builder.py    # Auto-schema generation from models
├── generator.py         # XLSX file generation with openpyxl
├── storage.py           # Storage backends (local, S3)
├── tasks.py             # Celery tasks for async export
├── mixins.py            # DRF ViewSet mixin
└── README.md            # This file
```

## Components

### ExportXLSXMixin

DRF ViewSet mixin that adds `/export/` action.

**Methods:**
- `export(request)` - Export action handler
- `get_export_data(request)` - Override for custom export
- `_generate_default_schema(request)` - Auto-generate from model
- `_get_export_filename()` - Generate filename

### XLSXGenerator

Generates Excel files from schema definitions.

**Usage:**
```python
from libs.export_xlsx import XLSXGenerator

generator = XLSXGenerator()
file_content = generator.generate(schema)  # Returns BytesIO
```

### SchemaBuilder

Automatically builds export schema from Django models.

**Usage:**
```python
from libs.export_xlsx import SchemaBuilder

builder = SchemaBuilder()
schema = builder.build_from_model(MyModel, queryset=MyModel.objects.all())
```

### Storage Backends

Handles file storage and URL generation.

**Usage:**
```python
from libs.export_xlsx import get_storage_backend

storage = get_storage_backend("s3")  # or "local"
file_path = storage.save(file_content, "export.xlsx")
file_url = storage.get_url(file_path)
```

### Celery Task

Background task for async export.

**Usage:**
```python
from libs.export_xlsx import generate_xlsx_task

task = generate_xlsx_task.delay(
    schema=schema,
    filename="export.xlsx",
    storage_backend="s3"
)
```

## Schema Format

```python
{
    "sheets": [
        {
            "name": "Sheet Name",
            "headers": ["Column 1", "Column 2", ...],
            "field_names": ["field1", "field2", ...],
            "data": [
                {"field1": "value1", "field2": "value2"},
                ...
            ],
            "groups": [  # Optional
                {"title": "Group 1", "span": 2},
                ...
            ],
            "merge_rules": ["field1", ...],  # Optional
        }
    ]
}
```

## Configuration

Settings in `settings/base/export.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `EXPORTER_CELERY_ENABLED` | `False` | Enable async export |
| `EXPORTER_STORAGE_BACKEND` | `local` | Storage backend (`local` or `s3`) |
| `EXPORTER_S3_BUCKET_NAME` | `""` | S3 bucket name (optional, uses `AWS_STORAGE_BUCKET_NAME` if not set) |
| `EXPORTER_S3_SIGNED_URL_EXPIRE` | `3600` | Signed URL expiration (seconds) |
| `EXPORTER_FILE_EXPIRE_DAYS` | `7` | Auto-delete after days |
| `EXPORTER_LOCAL_STORAGE_PATH` | `exports` | Local storage path |
| `EXPORTER_PROGRESS_CHUNK_SIZE` | `500` | Progress update frequency (rows) |

### Storage Backend Details

**Local Storage (`local`)**:
- Uses `FileSystemStorage` to save files to the local filesystem
- Files are saved to `MEDIA_ROOT/EXPORTER_LOCAL_STORAGE_PATH/`
- Independent of Django's `STORAGES` configuration
- URLs are served via Django's media URL

**S3 Storage (`s3`)**:
- Uses Django's `default_storage` (should be configured as S3)
- Generates signed URLs using boto3 for secure, time-limited access
- Respects `AWS_LOCATION` setting for file path prefix
- Signed URLs expire after `EXPORTER_S3_SIGNED_URL_EXPIRE` seconds (default: 1 hour)
- Falls back to standard storage URLs if signed URL generation fails

## Progress Tracking

The export module provides real-time progress tracking for async exports:

### Features

- **Progress percentage** (0-100%)
- **Rows processed** / **total rows**
- **Processing speed** (rows/second)
- **Estimated time to completion** (seconds)
- **Redis storage** for fast access
- **Celery task meta** for persistence

### How It Works

1. When an async export starts, it immediately returns a 202 response with a task ID
2. **Data fetching happens in the background**: The task fetches and processes data asynchronously, so the client doesn't wait
3. The task calculates the total number of rows and begins processing
4. As rows are written, progress is updated every N rows (configurable via `EXPORTER_PROGRESS_CHUNK_SIZE`)
5. Progress is published to:
   - **Redis** - for fast, real-time access
   - **Celery task meta** - for persistence and fallback
6. Clients poll the status endpoint to get progress updates

**Performance Optimization**: Both default exports (auto-generated from models) and custom exports defer all data fetching to the Celery worker. This ensures the initial API call returns immediately without waiting for potentially slow database queries or custom data processing logic, providing true asynchronous behavior for all export types.

### API Usage

Start an async export:
```bash
GET /api/my-endpoint/export/?async=true
```

Response:
```json
{
  "task_id": "abc123...",
  "status": "PENDING",
  "message": "Export started. Check status at /api/export/status/?task_id=abc123..."
}
```

Check export status with progress:
```bash
GET /api/core/export/status/?task_id=abc123...
```

Response (in progress):
```json
{
  "success": true,
  "data": {
    "task_id": "abc123...",
    "status": "PROGRESS",
    "percent": 45,
    "processed_rows": 4500,
    "total_rows": 10000,
    "speed_rows_per_sec": 125.5,
    "eta_seconds": 43.8,
    "updated_at": "2025-10-20T12:30:00"
  }
}
```

Response (completed):
```json
{
  "success": true,
  "data": {
    "task_id": "abc123...",
    "status": "SUCCESS",
    "percent": 100,
    "processed_rows": 10000,
    "total_rows": 10000,
    "file_url": "https://example.com/exports/data.xlsx",
    "file_path": "exports/data.xlsx"
  }
}
```

### Programmatic Access

```python
from libs.export_xlsx import get_progress

# Get progress for a task
progress = get_progress(task_id="abc123...")
if progress:
    print(f"Progress: {progress['percent']}%")
    print(f"Rows: {progress['processed_rows']}/{progress['total_rows']}")
    print(f"Speed: {progress.get('speed_rows_per_sec', 0)} rows/sec")
```

## Testing

Tests are located in `tests/libs/`:

- `test_export_xlsx.py` - Core functionality tests
- `test_export_xlsx_mixin.py` - ViewSet mixin tests

Run tests:
```bash
pytest tests/libs/test_export_xlsx*.py -v
```

## Examples

See `docs/XLSX_EXPORT_GUIDE.md` for comprehensive examples and best practices.

## Architecture

```
┌─────────────────────┐
│  DRF ViewSet        │
│  + ExportXLSXMixin  │
└──────────┬──────────┘
           │
           ├─ Sync: Direct response
           │
           └─ Async: Celery task
                     │
                     ├─ Generate XLSX (XLSXGenerator)
                     │
                     ├─ Save to Storage (Local/S3)
                     │
                     └─ Return URL
```

## License

Internal project module - not for public distribution.
