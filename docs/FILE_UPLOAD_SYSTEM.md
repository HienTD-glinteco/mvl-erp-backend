# Generic File Upload System

## Overview

This document describes the generic file upload system implemented in the `apps/files` module. The system provides a reusable, secure, and scalable solution for handling file uploads to Amazon S3 using a two-phase approach: **presign** (generate upload URL) and **confirm** (finalize upload).

## Key Features

- **Direct S3 Upload**: Files are uploaded directly to S3 from the client, bypassing Django for better performance
- **Generic Relations**: Files can be linked to any Django model using ContentType framework
- **Two-Phase Upload**: Temporary uploads are only confirmed when parent object is saved
- **Multiple Confirmation Options**: 
  - Manual confirmation via API endpoint for flexibility
  - Automatic confirmation via `FileConfirmSerializerMixin` for simplicity
- **Batch Operations**: Confirm multiple files in a single transaction
- **Automatic Cleanup**: Temporary files in `uploads/tmp/` can be auto-deleted by S3 lifecycle rules
- **Secure**: Presigned URLs expire after 1 hour
- **Content Type Validation**: Validates actual file content matches declared type
- **Migration-Free**: New file purposes don't require database migrations
- **Presigned View/Download URLs**: Generate secure URLs for viewing and downloading files

## Architecture

### Data Model

The system uses a single `FileModel` with Generic Foreign Keys:

```python
class FileModel(BaseModel):
    purpose = CharField(max_length=100)          # e.g., "job_description", "invoice"
    file_name = CharField(max_length=255)        # Original filename
    file_path = CharField(max_length=500)        # S3 path
    size = BigIntegerField(null=True, blank=True)  # File size in bytes
    checksum = CharField(max_length=64, null=True, blank=True)  # MD5 checksum (ETag)
    is_confirmed = BooleanField(default=False)   # Confirmation status
    uploaded_by = ForeignKey("core.User", null=True, blank=True)  # User who uploaded
    
    # Generic Foreign Key
    content_type = ForeignKey(ContentType, null=True, blank=True)
    object_id = PositiveIntegerField(null=True, blank=True)
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
- Permanent: `uploads/employee_cv/42/CV.pdf` (purpose: `employee_cv`, object_id: `42`)

## Integration Methods

The system supports two integration approaches:

| Aspect | Manual Confirmation | FileConfirmSerializerMixin |
|--------|-------------------|---------------------------|
| **API Calls** | 3 separate calls (presign, upload to S3, confirm) | 2 calls (presign + upload to S3, then create object with files) |
| **Transaction Safety** | Manual transaction handling | Automatic (files + object in one transaction) |
| **Use Case** | Files linked to different objects, pre-upload scenarios | Files belong to single object, atomic operations |
| **Complexity** | More control, more code | Less code, simpler frontend |
| **Best For** | Complex workflows, multiple related objects | Standard CRUD with file attachments |

**Quick Start**:
- New to the system? → Use **FileConfirmSerializerMixin** (Option 3 in Backend Integration)
- Need fine control? → Use **Manual Confirmation** (see API Endpoints below)

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

### 2. Confirm File Upload(s)

**Endpoint**: `POST /api/files/confirm/`

**Authentication**: Required

**Request Body**:
```json
{
  "files": [
    {
      "file_token": "f7e3c91a-b32a-4c6d-bbe2-8c9f2a6a9f32",
      "purpose": "employee_cv",
      "related_model": "hrm.Employee",
      "related_object_id": 42,
      "related_field": "cv_file"
    },
    {
      "file_token": "a2b5d8e1-c43f-4a7d-9be3-7d8e3f5a6b21",
      "purpose": "employee_document",
      "related_model": "hrm.Employee",
      "related_object_id": 42
    }
  ]
}
```

**Request Parameters**:
- `files`: Array of file configurations to confirm
  - `file_token` (required): Token returned by presign endpoint
  - `purpose` (required): File purpose (e.g., 'employee_cv', 'invoice')
  - `related_model` (required): Django model label (e.g., 'hrm.Employee')
  - `related_object_id` (required): ID of the related object
  - `related_field` (optional): Field name on related model to set as ForeignKey to this file

**Response**:
```json
{
  "success": true,
  "data": {
    "confirmed_files": [
      {
        "id": 112,
        "purpose": "employee_cv",
        "file_name": "document.pdf",
        "file_path": "uploads/employee_cv/42/document.pdf",
        "size": 123456,
        "checksum": "abc123def456",
        "is_confirmed": true,
        "uploaded_by": 5,
        "uploaded_by_username": "john_doe",
        "view_url": "https://s3.amazonaws.com/bucket/uploads/employee_cv/42/document.pdf?...",
        "download_url": "https://s3.amazonaws.com/bucket/uploads/employee_cv/42/document.pdf?response-content-disposition=attachment...",
        "created_at": "2025-10-16T04:00:00Z",
        "updated_at": "2025-10-16T04:00:00Z"
      },
      {
        "id": 113,
        "purpose": "employee_document",
        "file_name": "certificate.pdf",
        "file_path": "uploads/employee_document/42/certificate.pdf",
        "size": 234567,
        "checksum": "def789ghi012",
        "is_confirmed": true,
        "uploaded_by": 5,
        "uploaded_by_username": "john_doe",
        "view_url": "https://s3.amazonaws.com/bucket/uploads/employee_document/42/certificate.pdf?...",
        "download_url": "https://s3.amazonaws.com/bucket/uploads/employee_document/42/certificate.pdf?response-content-disposition=attachment...",
        "created_at": "2025-10-16T04:00:00Z",
        "updated_at": "2025-10-16T04:00:00Z"
      }
    ]
  },
  "error": null
}
```

**Response includes**:
- `confirmed_files`: Array of confirmed file records
  - `uploaded_by`: ID of the user who uploaded the file
  - `uploaded_by_username`: Username of the user who uploaded the file
  - `view_url`: Presigned URL for viewing the file inline (valid for 1 hour)
  - `download_url`: Presigned URL for downloading the file with original filename (valid for 1 hour)

**What happens**:
1. Validates all file tokens from cache
2. Verifies all files exist in S3 temporary locations
3. **Validates actual file content type matches expected type for each file** - If mismatch, deletes temp file and returns error
4. Validates all related objects exist
5. Moves all files from temporary to permanent locations
6. Creates FileModel records with Generic Foreign Keys (all in a single transaction)
7. Optionally sets ForeignKey on related objects (if `related_field` provided)
8. Deletes cache entries
9. Returns all confirmed file records with presigned URLs for viewing and downloading

**Notes**:
- All files are confirmed in a single database transaction
- If any file fails validation, the entire operation is rolled back
- Each file can have its own `related_model`, `related_object_id`, and `related_field`
- You can confirm multiple files for the same or different objects in one request

### 3. View and Download Files

Once a file is confirmed, you can access it through presigned URLs. These URLs are dynamically generated and included in API responses.

**File Access URLs**:
- **`view_url`**: Opens the file inline in the browser (for PDFs, images, etc.)
- **`download_url`**: Forces download with the original filename

These URLs are:
- Valid for 1 hour from generation time
- Regenerated on each API request that returns FileModel data
- Secure and don't require authentication once generated

**Frontend Usage**:
```javascript
// From confirm response or any endpoint returning FileModel
const confirmedFile = response.data.confirmed_files[0];
const { view_url, download_url } = confirmedFile;

// Open file in new tab (inline viewing)
window.open(view_url, '_blank');

// Download file
window.location.href = download_url;

// Or use fetch for more control
fetch(download_url)
  .then(response => response.blob())
  .then(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = confirmedFile.file_name;
    a.click();
  });
```

**Backend Usage**:
```python
from apps.files.models import FileModel

# Get file record
file_record = FileModel.objects.get(id=112)

# Access presigned URLs (properties that generate URLs on-the-fly)
view_url = file_record.view_url  # Presigned URL for viewing
download_url = file_record.download_url  # Presigned URL for downloading

# Include in API response (serializer handles this automatically)
from apps.files.api.serializers import FileSerializer
serializer = FileSerializer(file_record)
# serializer.data will include view_url and download_url
```

**Note**: If you need to list files for an object, use the Generic Foreign Key relationship:
```python
# Get all files for an object
employee = Employee.objects.get(id=42)
files = FileModel.objects.filter(
    content_type=ContentType.objects.get_for_model(Employee),
    object_id=employee.id,
    is_confirmed=True
)
```

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

// Step 4: Confirm file upload(s)
await fetch('/api/files/confirm/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    files: [
      {
        file_token: file_token,
        purpose: 'employee_cv',
        related_model: 'hrm.Employee',
        related_object_id: employeeId,
        related_field: 'cv_file'  // Optional: automatically sets employee.cv_file = file_record
      }
    ]
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

When confirming the upload, pass the file configurations in an array:

```json
{
  "files": [
    {
      "file_token": "...",
      "purpose": "employee_cv",
      "related_model": "hrm.Employee",
      "related_object_id": 42,
      "related_field": "cv_file"  // This will set employee.cv_file = file_record
    }
  ]
}
```

#### Option 3: Using FileConfirmSerializerMixin (Recommended)

For a simpler workflow that automatically confirms files when saving the parent object, use the `FileConfirmSerializerMixin`:

**Step 1: Add the mixin to your serializer**

```python
from rest_framework import serializers
from libs.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.models import JobDescription

class JobDescriptionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    # Note: 'files' field is automatically added by the mixin
    
    class Meta:
        model = JobDescription
        fields = [
            "id",
            "title",
            "responsibility",
            "requirement",
            "benefit",
            "proposed_salary",
            # Don't include 'files' in fields - it's added automatically
        ]
```

**Step 2: Update your model to have ForeignKey fields for files**

```python
from apps.files.models import FileModel

class JobDescription(models.Model):
    title = models.CharField(max_length=200)
    # ... other fields ...
    
    # ForeignKey to FileModel for direct file access
    attachment = models.ForeignKey(
        FileModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='job_description_attachments'
    )
    document = models.ForeignKey(
        FileModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='job_description_documents'
    )
```

**Step 3: Frontend workflow**

```javascript
// 1. Upload files via presigned URLs
const presignResponse1 = await fetch('/api/files/presign/', {
  method: 'POST',
  body: JSON.stringify({
    file_name: 'JD.pdf',
    file_type: 'application/pdf',
    purpose: 'job_description'
  })
});
const { upload_url: url1, file_token: token1 } = presignResponse1.data;

await fetch(url1, { method: 'PUT', body: file1, headers: { 'Content-Type': 'application/pdf' } });

// Repeat for second file...
const { file_token: token2 } = presignResponse2.data;

// 2. Create JobDescription with files in one request
await fetch('/api/hrm/job-descriptions/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'Senior Developer',
    responsibility: '...',
    requirement: '...',
    benefit: '...',
    proposed_salary: '$100k-$120k',
    files: {
      attachment: token1,  // Maps to JobDescription.attachment field
      document: token2     // Maps to JobDescription.document field
    }
  })
});
```

**How it works**:
1. The mixin adds a `files` field to the serializer that accepts a dictionary mapping field names to file tokens
2. When the serializer saves the instance, it automatically:
   - Validates all file tokens exist in cache
   - Verifies files exist in S3 temporary storage
   - Validates content types match expected types
   - Moves files from temp to permanent storage
   - Creates FileModel records linked via Generic Foreign Keys
   - **Assigns files to the specified model fields** (e.g., `attachment` field gets the file)
   - All in a single database transaction
3. If any step fails, the entire operation (including model creation) is rolled back

**Benefits**:
- ✅ Single API call to create object and confirm files
- ✅ Automatic transaction management
- ✅ Cleaner frontend code
- ✅ Files are automatically linked to model fields
- ✅ No separate confirmation endpoint needed
- ✅ Consistent error handling

**Limitations**:
- Files must be linked to the same parent object
- Each file token can only map to one model field
- Model must be created/updated for files to be confirmed

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

**Invalid or expired token**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "detail": "Invalid or expired file token: abc123"
  }
}
```

**File already confirmed**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "detail": "File has already been confirmed: abc123"
  }
}
```

**File not found in S3**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "detail": "File not found in S3: abc123"
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

**Related object not found**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "related_object_id": ["Object with ID 99999 not found"]
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

# Run specific test files
poetry run pytest apps/files/tests/test_file_upload_api.py -v
poetry run pytest apps/files/tests/test_s3_utils.py -v
poetry run pytest apps/files/tests/test_file_confirm_mixin.py -v
```

Test coverage:
- Presign URL generation (success, errors, authentication)
- File type validation (allowed/disallowed types)
- Content type verification (prevents type spoofing)
- Multiple file confirmation (success, errors, edge cases)
- Single vs multiple file scenarios
- S3 operations (presign, move, delete, metadata - all mocked)
- FileModel CRUD operations
- ForeignKey relationship handling
- FileConfirmSerializerMixin functionality

## Integration Options

### Option 1: Manual Confirmation via API Endpoint

Best for scenarios where:
- Files need to be confirmed separately from object creation
- Multiple objects need to reference the same files
- Files are uploaded before knowing the related object ID

**Workflow**:
1. Upload files via presigned URLs
2. Create/update your object
3. Call `/api/files/confirm/` with file tokens and object IDs

### Option 2: FileConfirmSerializerMixin (Recommended)

Best for scenarios where:
- Files belong to a single object
- You want to create/update object and confirm files in one request
- You want simpler frontend code
- You need atomic transaction guarantees

**Workflow**:
1. Upload files via presigned URLs
2. Create/update your object with `files` dict in request body
3. Files are automatically confirmed when object is saved

## Future Enhancements

Potential improvements (not yet implemented):

1. **MD5 Checksum Validation**: Client computes checksum, backend validates
2. **File Versioning**: Track multiple versions per related object
3. ~~**Signed GET URLs**: Generate presigned URLs for secure downloads~~ (✅ Already implemented)
4. **Multi-part Upload**: Support for files larger than 5GB
5. **Virus Scanning**: Integrate ClamAV or AWS Lambda for scanning
6. **Thumbnail Generation**: Auto-generate thumbnails for images
7. **Bulk File Operations**: Delete/move multiple files at once

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
