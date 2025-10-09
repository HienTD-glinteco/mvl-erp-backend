# XLSX Export Module

Dynamic XLSX exporter for Django REST Framework with support for async processing and multiple storage backends.

## Features

- ✅ **Auto-schema generation** from Django models
- ✅ **Custom export schemas** with full control
- ✅ **Nested data support** with automatic flattening
- ✅ **Merged cells** for grouped data visualization
- ✅ **Multi-level headers** with grouping
- ✅ **Async export** via Celery (optional)
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
GET /api/my-endpoint/download/

# Asynchronous export (requires Celery)
GET /api/my-endpoint/download/?async=true
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

DRF ViewSet mixin that adds `/download/` action.

**Methods:**
- `download(request)` - Export action handler
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
| `EXPORTER_STORAGE_BACKEND` | `local` | Storage backend |
| `EXPORTER_S3_BUCKET_NAME` | `""` | S3 bucket name |
| `EXPORTER_S3_SIGNED_URL_EXPIRE` | `3600` | URL expiration (seconds) |
| `EXPORTER_FILE_EXPIRE_DAYS` | `7` | Auto-delete after days |
| `EXPORTER_LOCAL_STORAGE_PATH` | `exports` | Local storage path |

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
