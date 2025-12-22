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
    "file_type": "application/pdf",
    "purpose": "job_description"
  }'
```

### 2. Upload to S3

```bash
curl -X PUT "PRESIGNED_URL_FROM_STEP_1" \
  -H "Content-Type: application/pdf" \
  --data-binary @document.pdf
```

### 3. Confirm File Upload(s)

Each file can be confirmed individually with its own related object and optional field assignment:

```bash
curl -X POST http://localhost:8000/api/files/confirm/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {
        "file_token": "TOKEN_1",
        "purpose": "job_description",
        "related_model": "hrm.JobDescription",
        "related_object_id": 15,
        "related_field": "attachment"
      },
      {
        "file_token": "TOKEN_2",
        "purpose": "job_description",
        "related_model": "hrm.JobDescription",
        "related_object_id": 15
      }
    ]
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
- **ConfirmMultipleFilesView**: Confirms multiple uploads in a single transaction

### Serializers

- **PresignRequestSerializer**: Validates presign requests
- **ConfirmMultipleFilesSerializer**: Validates multiple file confirmation
- **ConfirmMultipleFilesResponseSerializer**: Response serializer for multi-file confirmation
- **FileSerializer**: Serializes FileModel instances

### Utilities

- **S3FileUploadService**: Handles all S3 operations (presign, check, move, metadata)

### Mixins

- **FileConfirmSerializerMixin**: Auto-confirms files when serializer is saved (New)

## Using FileConfirmSerializerMixin

The `FileConfirmSerializerMixin` enables automatic file confirmation during serializer save, eliminating the need for a separate confirmation API call.

### Example Usage

```python
from rest_framework import serializers
from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.models import JobDescription

class JobDescriptionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    # Specify which fields should show up in 'files' object
    file_confirm_fields = ['attachment', 'document']

    # Optional: specify required file fields
    file_required_fields = ['attachment']

    class Meta:
        model = JobDescription
        fields = [
            "id",
            "code",
            "title",
            "responsibility",
            "requirement",
            "benefit",
            "proposed_salary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at"]
```

### Multi-valued and Required Fields

The mixin supports various configurations for the `files` field:

- `file_confirm_fields`: Explicit list of field names that represent files.
- `file_multi_valued_fields`: Fields that accept multiple files (e.g., `GenericRelation` or `ManyToManyField`).
- `file_required_fields`: Fields that MUST be provided during creation/update.

### Workflow

1. Frontend uploads files via presigned URLs and receives `file_tokens`
2. Frontend submits form data with `files` dict mapping field names to tokens:

```json
{
  "title": "Senior Developer",
  "responsibility": "Lead development team...",
  "requirement": "5+ years experience...",
  "benefit": "Competitive salary...",
  "proposed_salary": "$100k-$120k",
  "files": {
    "attachment": "abc123",
    "document": "xyz789"
  }
}
```

3. The mixin automatically:
   - Validates all file tokens
   - Confirms files exist in S3
   - Moves files from temp to permanent storage
   - Links files to the created/updated instance
   - **Assigns files to the specified model fields** (e.g., `attachment` field gets the file)
   - All in a single database transaction

### Features

- ✅ Automatic file confirmation on save
- ✅ Transaction safety (rollback if confirmation fails)
- ✅ Supports multiple files with field assignments
- ✅ Validates content types
- ✅ Links files via Generic Relations
- ✅ Assigns files directly to model fields
- ✅ Cleans up cache after confirmation

## Testing

Run tests:
```bash
poetry run pytest apps/files/tests/ -v
```

Test coverage includes:
- ✅ Presign URL generation
- ✅ Single file confirmation
- ✅ Multiple file confirmation (New)
- ✅ FileConfirmSerializerMixin (New)
- ✅ S3 utilities
- ✅ Error handling and validation

## Documentation

See [FILE_UPLOAD_SYSTEM.md](../../docs/FILE_UPLOAD_SYSTEM.md) for complete documentation.
