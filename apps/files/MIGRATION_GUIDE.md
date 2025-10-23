# File Storage Migration Guide

## Overview

This guide explains the changes made to support storage prefix (AWS_LOCATION) in S3 file paths and nullable related fields in the confirm endpoint.

## Changes Summary

### 1. Storage Prefix Support

The file storage system now properly handles the AWS_LOCATION storage prefix (e.g., `media/`) in all S3 operations.

**Key Changes:**
- All S3 keys now include the storage prefix when configured
- Presigned URLs, file moves, and path generation respect the prefix
- Backward compatibility helper resolves paths without prefix

**Example:**
```python
# With AWS_LOCATION = "media"
# Old path: uploads/job_description/15/file.pdf
# New path: media/uploads/job_description/15/file.pdf
```

### 2. Nullable Related Fields

The confirm endpoint now supports file uploads without related objects (e.g., for import jobs).

**Key Changes:**
- `related_model` and `related_object_id` are now optional in FileConfirmationSerializer
- Files without related objects are stored under `uploads/{purpose}/unrelated/{uuid}/` path
- Validation ensures both related fields are provided together or both omitted

**Example:**
```json
{
  "files": [
    {
      "file_token": "abc-123",
      "purpose": "import_data"
      // No related_model or related_object_id
    }
  ]
}
```

## Migration Instructions

### Step 1: Deploy Code Changes

Deploy the updated code to your environment. The code includes backward compatibility, so existing functionality will continue to work.

### Step 2: Run Migration (Dry Run)

First, run the migration command in dry-run mode to see what would be changed:

```bash
python manage.py files_migrate_paths --dry-run
```

This will report:
- Total records without prefix
- Records that would be updated (S3 object exists at prefixed path)
- Records where S3 object is not found at prefixed path

### Step 3: Review Results

Review the dry-run output carefully:
- **Records to update**: Normal migration candidates
- **Objects not found**: May need manual investigation (file might not exist in S3, or path might be incorrect)

### Step 4: Apply Migration

Once satisfied with the dry-run results, apply the migration:

```bash
python manage.py files_migrate_paths --apply
```

For large datasets, you can process in batches:

```bash
python manage.py files_migrate_paths --apply --limit 1000
```

### Step 5: Monitor

After migration:
1. Check application logs for any file access errors
2. Verify that file URLs are working correctly
3. Monitor S3 access patterns

## Rollback Plan

If issues occur:

1. **Revert Code**: Deploy previous version
2. **Database Rollback**: If needed, revert `file_path` values in the database using backup

Note: The code includes `resolve_actual_storage_key()` which provides runtime fallback for mixed scenarios.

## Technical Details

### New Utilities

**`apps/files/utils/storage_utils.py`**
- `get_storage_prefix()`: Gets configured storage prefix from settings
- `build_storage_key()`: Constructs S3 keys with prefix
- `resolve_actual_storage_key()`: Resolves actual S3 key (backward compatibility)

### Updated Components

**`apps/files/utils/s3_utils.py`**
- `generate_presigned_url()`: Includes prefix in temp keys
- `generate_permanent_path()`: Supports nullable related fields, includes prefix
- `move_file()`: Added retry logic with exponential backoff

**`apps/files/api/serializers/file_serializers.py`**
- `FileConfirmationSerializer`: Made `related_model` and `related_object_id` optional
- Added validation to ensure both fields are provided together or both omitted

**`apps/files/api/views/file_views.py`**
- `ConfirmMultipleFilesView`: Updated to handle nullable related fields

### Management Command

**`apps/files/management/commands/files_migrate_paths.py`**
- Scans FileModel records without prefix
- Checks if S3 object exists at prefixed path
- Updates database records (with --apply flag)
- Provides detailed reporting

## Testing

Run the test suite to verify functionality:

```bash
# Run all file tests
pytest apps/files/tests/ -v

# Run specific test files
pytest apps/files/tests/test_storage_utils.py -v
pytest apps/files/tests/test_s3_utils.py -v
pytest apps/files/tests/test_serializers.py -v
```

## Configuration

Ensure these settings are properly configured:

```python
# settings/base/aws.py
AWS_LOCATION = "media"  # Storage prefix

# settings/base/storage.py
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
        },
    },
}
```

## API Changes

### Confirm Endpoint

The confirm endpoint now accepts requests without related fields:

**With related object (existing behavior):**
```json
{
  "files": [
    {
      "file_token": "abc-123",
      "purpose": "job_description",
      "related_model": "hrm.JobDescription",
      "related_object_id": 15
    }
  ]
}
```

**Without related object (new feature):**
```json
{
  "files": [
    {
      "file_token": "xyz-456",
      "purpose": "import_data"
    }
  ]
}
```

## Troubleshooting

### Files Not Accessible After Migration

**Issue**: Files return 404 or access denied errors

**Solution**:
1. Check if S3 objects exist at the expected paths
2. Verify AWS_LOCATION setting matches S3 structure
3. Run `resolve_actual_storage_key()` to diagnose path issues

### Migration Shows Many "Object Not Found"

**Issue**: Many records show S3 object not found during migration

**Possible Causes**:
1. Files were deleted from S3 but records remain in database
2. Files were uploaded before the system was fully configured
3. AWS_LOCATION setting doesn't match actual S3 structure

**Solution**:
1. Manually verify a sample of these records in S3
2. Consider cleaning up orphaned database records
3. Contact DevOps to verify S3 bucket structure

## Support

For issues or questions:
1. Check application logs for detailed error messages
2. Run migration in dry-run mode to diagnose issues
3. Contact the backend team for assistance
