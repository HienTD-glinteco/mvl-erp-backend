# Files App

Generic file upload system for handling S3 uploads with presign and confirm flow.

## Quick Start

### 1. Generate Presigned URL

```bash
curl -X POST http://localhost:8000/api/files/presign/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "document.pdf",
    "file_size": 123456,
    "purpose": "job_description"
  }'
```

### 2. Upload to S3

```bash
curl -X PUT "PRESIGNED_URL_FROM_STEP_1" \
  -H "Content-Type: application/pdf" \
  --data-binary @document.pdf
```

### 3. Confirm Upload

```bash
curl -X POST http://localhost:8000/api/files/confirm/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_token": "TOKEN_FROM_STEP_1",
    "related_model": "hrm.Employee",
    "related_object_id": 42,
    "purpose": "job_description"
  }'
```

## Module Structure

```
apps/files/
├── __init__.py
├── admin.py              # Django admin configuration
├── apps.py               # App configuration
├── constants.py          # API constants and error messages
├── models.py             # FileModel with Generic Relations
├── urls.py               # URL routing
├── api/
│   ├── serializers/
│   │   └── file_serializers.py    # Request/response serializers
│   └── views/
│       └── file_views.py          # Presign and confirm views
├── utils/
│   └── s3_utils.py       # S3 client utilities
├── migrations/
│   └── 0001_initial.py   # Initial migration
└── tests/
    ├── test_file_upload_api.py    # API endpoint tests
    └── test_s3_utils.py           # S3 utilities tests
```

## Key Components

### Models

- **FileModel**: Main model with Generic Foreign Key to link files to any Django model

### API Views

- **PresignURLView**: Generates presigned S3 upload URLs
- **ConfirmFileUploadView**: Confirms upload and moves file to permanent storage

### Utilities

- **S3FileUploadService**: Handles all S3 operations (presign, check, move, metadata)

## Testing

Run tests:
```bash
poetry run pytest apps/files/tests/ -v
```

All 22 tests should pass.

## Documentation

See [FILE_UPLOAD_SYSTEM.md](../../docs/FILE_UPLOAD_SYSTEM.md) for complete documentation.
