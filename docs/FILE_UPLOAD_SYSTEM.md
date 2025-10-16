# Generic File Upload System

## Overview

This document describes the generic file upload system implemented in the `apps/files` module. The system provides a reusable, secure, and scalable solution for handling file uploads to Amazon S3 using a two-phase approach: **presign** (generate upload URL) and **confirm** (finalize upload).

## Key Features

- **Direct S3 Upload**: Files are uploaded directly to S3 from the client, bypassing Django for better performance
- **Generic Relations**: Files can be linked to any Django model using ContentType framework
- **Two-Phase Upload**: Temporary uploads are only confirmed when parent object is saved
- **Automatic Cleanup**: Temporary files in `uploads/tmp/` can be auto-deleted by S3 lifecycle rules
- **Secure**: Presigned URLs expire after 1 hour
- **Migration-Free**: New file purposes don't require database migrations

## Architecture

### Data Model

The system uses a single `FileModel` with Generic Foreign Keys:

```python
class FileModel(BaseModel):
    purpose = CharField(max_length=100)          # e.g., "job_description", "invoice"
    file_name = CharField(max_length=255)        # Original filename
    file_path = CharField(max_length=500)        # S3 path
    size = BigIntegerField()                     # File size in bytes
    checksum = CharField(max_length=64)          # MD5 checksum (ETag)
    is_confirmed = BooleanField(default=False)   # Confirmation status
    
    # Generic Foreign Key
    content_type = ForeignKey(ContentType)
    object_id = PositiveIntegerField()
    related_object = GenericForeignKey("content_type", "object_id")
```

### S3 Structure

```
uploads/
├── tmp/                              # Temporary uploads (auto-cleanup after 24h)
│   └── {file_token}/
│       └── {filename}
└── {purpose}/                        # Permanent storage
    └── {object_id}/
        └── {filename}
```

Example paths:
- Temporary: `uploads/tmp/f7e3c91a-b32a-4c6d-bbe2-8c9f2a6a9f32/CV.pdf`
- Permanent: `uploads/employee/42/CV.pdf`

## API Endpoints

### 1. Generate Presigned URL

**Endpoint**: `POST /api/files/presign/`

**Authentication**: Required

**Request Body**:
```json
{
  "file_name": "document.pdf",
  "file_type": "application/pdf",
  "purpose": "job_description"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "upload_url": "https://s3.amazonaws.com/bucket/uploads/tmp/uuid/document.pdf?...",
    "file_path": "uploads/tmp/uuid/document.pdf",
    "file_token": "f7e3c91a-b32a-4c6d-bbe2-8c9f2a6a9f32"
  },
  "error": null
}
```

**What happens**:
1. System validates file type is allowed for the specified purpose
2. Generates unique file token and temporary S3 path
3. Creates presigned PUT URL with ContentType in signature (expires in 1 hour)
4. Stores file metadata in cache (expires in 1 hour)
5. Returns upload URL and token to client

**File Type Validation**: The system enforces allowed file types per purpose. For example:
- `job_description`: PDF, DOC, DOCX
- `employee_cv`: PDF, DOC, DOCX
- `invoice`: PDF, PNG, JPEG
- `profile_picture`: PNG, JPEG, JPG, WEBP

### 2. Confirm File Upload

**Endpoint**: `POST /api/files/confirm/`

**Authentication**: Required

**Request Body**:
```json
{
  "file_token": "f7e3c91a-b32a-4c6d-bbe2-8c9f2a6a9f32",
  "related_model": "hrm.Employee",
  "related_object_id": 42,
  "purpose": "employee_cv",
  "related_field": "cv_file"  // Optional: sets employee.cv_file = file_record
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": 112,
    "purpose": "employee_cv",
    "file_name": "document.pdf",
    "file_path": "uploads/employee_cv/42/document.pdf",
    "size": 123456,
    "checksum": "abc123def456",
    "is_confirmed": true,
    "created_at": "2025-10-16T04:00:00Z",
    "updated_at": "2025-10-16T04:00:00Z"
  },
  "error": null
}
```

**What happens**:
1. Validates file token from cache
2. Verifies file exists in S3 temporary location
3. **Validates actual file content type matches expected type** - If mismatch, deletes temp file and returns error
4. Validates related object exists
5. Moves file from temporary to permanent location
6. Creates FileModel record with Generic Foreign Key
7. Optionally sets ForeignKey on related object (if `related_field` provided)
8. Deletes cache entry

## Usage Example

### Frontend Flow

```javascript
// Step 1: Get presigned URL
const presignResponse = await fetch('/api/files/presign/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    file_name: 'CV.pdf',
    file_type: file.type,  // e.g., 'application/pdf'
    purpose: 'employee_cv'
  })
});

const { upload_url, file_token } = presignResponse.data;

// Step 2: Upload file directly to S3
// IMPORTANT: Must include Content-Type header matching the file_type from step 1
await fetch(upload_url, {
  method: 'PUT',
  body: file,
  headers: {
    'Content-Type': file.type
  }
});

// Step 3: Save parent object (e.g., Employee)
const employeeResponse = await fetch('/api/hrm/employees/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    first_name: 'John',
    last_name: 'Doe',
    // ... other fields
  })
});

const { id: employeeId } = employeeResponse.data;

// Step 4: Confirm file upload
await fetch('/api/files/confirm/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    file_token: file_token,
    related_model: 'hrm.Employee',
    related_object_id: employeeId,
    purpose: 'employee_cv',
    related_field: 'cv_file'  // Optional: automatically sets employee.cv_file = file_record
  })
});
```

### Backend Integration

#### Option 1: Using Generic Relations (Many files per object)

To link multiple files to your model, add a GenericRelation:

```python
from django.contrib.contenttypes.fields import GenericRelation
from apps.files.models import FileModel

class Employee(models.Model):
    # ... your fields ...
    
    # Add this to enable reverse lookup for multiple files
    files = GenericRelation(FileModel)
    
    def get_cv(self):
        """Get employee CV file."""
        return self.files.filter(purpose='employee_cv').first()
```

#### Option 2: Using ForeignKey (Single file per object)

For cases where you want a direct ForeignKey relationship (one file per purpose), use the `related_field` parameter:

```python
from apps.files.models import FileModel

class Employee(models.Model):
    # ... your fields ...
    
    # Direct ForeignKey to file
    cv_file = models.ForeignKey(
        FileModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_cv'
    )
    
    profile_picture = models.ForeignKey(
        FileModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_profile'
    )
```

When confirming the upload, pass `related_field` to automatically set the ForeignKey:

```json
{
  "file_token": "...",
  "related_model": "hrm.Employee",
  "related_object_id": 42,
  "purpose": "employee_cv",
  "related_field": "cv_file"  // This will set employee.cv_file = file_record
}
```

## Configuration

### File Type Restrictions

Configure allowed file types per purpose in `apps/files/constants.py`:

```python
ALLOWED_FILE_TYPES = {
    "job_description": [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ],
    "employee_cv": [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ],
    "invoice": [
        "application/pdf",
        "image/png",
        "image/jpeg",
    ],
    "profile_picture": [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
    ],
}
```

If a purpose is not in this dictionary, all file types are allowed. Add new purposes as needed without migrations.

### Cache Settings

The system uses Django cache to store file tokens. For production, configure Redis:

```python
# settings/prod.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/0",
    }
}
```

For testing, LocMemCache is used automatically.

### S3 Lifecycle Rule

To automatically clean up unconfirmed uploads, configure S3 lifecycle policy:

```json
{
  "Rules": [
    {
      "Id": "DeleteTempUploads",
      "Status": "Enabled",
      "Prefix": "uploads/tmp/",
      "Expiration": {
        "Days": 1
      }
    }
  ]
}
```

## File Purposes

File purposes are simple strings that determine the final S3 folder. Common examples:

- `job_description` - Job description documents
- `employee_cv` - Employee CVs/resumes
- `invoice` - Invoice documents
- `contract` - Contract documents
- `profile_picture` - User profile pictures

No code changes or migrations are needed to add new purposes.

## Security Considerations

1. **Presigned URLs**: Expire after 1 hour, limiting upload window
2. **Authentication**: Both endpoints require authentication
3. **File Type Validation**: System validates actual content type of uploaded file before confirmation
   - Client cannot bypass validation by sending wrong content type
   - If content type mismatch detected, temp file is automatically deleted
   - Returns detailed error with expected vs actual content type
4. **ContentType in Signature**: ContentType included in presigned URL signature prevents type spoofing
5. **Token-based**: File token stored in cache prevents unauthorized confirmations
6. **Related Object Validation**: Confirm endpoint validates related object exists
7. **S3 Permissions**: Presigned URLs only allow PUT operation

## Error Handling

### Common Error Responses

**Invalid token**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "detail": "Invalid or expired file token"
  }
}
```

**File not found in S3**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "detail": "File not found in S3"
  }
}
```

**Invalid related model**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "related_model": ["Invalid model label: invalid.Model"]
  }
}
```

**Content type mismatch** (uploaded file type doesn't match declared type):
```json
{
  "success": false,
  "data": null,
  "error": {
    "detail": "Uploaded file content type does not match expected type",
    "expected": "application/pdf",
    "actual": "application/x-msdownload"
  }
}
```

**Note**: When content type mismatch is detected, the system automatically deletes the uploaded file from S3 for security.

## Testing

The system includes comprehensive tests:

```bash
# Run all file upload tests
poetry run pytest apps/files/tests/ -v

# Run specific test file
poetry run pytest apps/files/tests/test_file_upload_api.py -v
poetry run pytest apps/files/tests/test_s3_utils.py -v
```

Test coverage:
- Presign URL generation (success, errors, authentication)
- File type validation (allowed/disallowed types)
- Content type verification (prevents type spoofing)
- File confirmation (success, errors, edge cases)
- S3 operations (presign, move, delete, metadata - all mocked)
- FileModel CRUD operations
- ForeignKey relationship handling

## Future Enhancements

Potential improvements (not yet implemented):

1. **MD5 Checksum Validation**: Client computes checksum, backend validates
2. **File Versioning**: Track multiple versions per related object
3. **Signed GET URLs**: Generate presigned URLs for secure downloads
4. **Multi-part Upload**: Support for files larger than 5GB
5. **Virus Scanning**: Integrate ClamAV or AWS Lambda for scanning
6. **Thumbnail Generation**: Auto-generate thumbnails for images
7. **File Metadata**: Store MIME type, dimensions for images, etc.

## Troubleshooting

### Issue: XML error response when uploading to presigned URL

**Problem**: Client receives XML error response like `<?xml version="1.0" encoding="UTF-8"?>` when attempting to upload to the presigned URL.

**Solution**: This was fixed by removing the `ContentLength` parameter from presigned URL generation. The `ContentLength` should be sent in the request headers by the client, not included in the presigned URL parameters. The fix ensures the presigned URL only contains the necessary S3 parameters (Bucket, Key).

**Client-side note**: When uploading, the client should include the `Content-Length` header in their PUT request to S3.

### Issue: Cache not working

**Problem**: File tokens not persisting between presign and confirm.

**Solution**: Check cache configuration. In development, ensure `CACHES` setting uses LocMemCache or Redis, not DummyCache.

### Issue: S3 permissions error

**Problem**: Presigned URL generation fails with permission error.

**Solution**: Verify AWS credentials in `.env`:
```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_STORAGE_BUCKET_NAME=your_bucket
AWS_REGION_NAME=us-east-1
```

### Issue: File not found after upload

**Problem**: Confirm endpoint reports file not found in S3.

**Solution**: 
1. Ensure client successfully uploaded to presigned URL
2. Check if upload completed before confirmation
3. Verify network connectivity to S3

## References

- Django ContentTypes Framework: https://docs.djangoproject.com/en/5.0/ref/contrib/contenttypes/
- AWS S3 Presigned URLs: https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html
- Django Cache Framework: https://docs.djangoproject.com/en/5.0/topics/cache/
