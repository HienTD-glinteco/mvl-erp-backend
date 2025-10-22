# Storage Prefix Fix - Critical Update

## Problem Identified

The original implementation had a critical flaw: it stored the storage prefix (AWS_LOCATION = `"media"`) in `FileModel.file_path`, which caused double-prefixing when using Django's `default_storage`.

### What Went Wrong

```python
# Original (incorrect) implementation:
file_path = "media/uploads/job_description/15/file.pdf"  # Stored in DB

# When accessing:
default_storage.open(file_path)
# S3Boto3Storage adds location: "media/" + "media/uploads/..." 
# Result: "media/media/uploads/..." ❌ FILE NOT FOUND
```

### Root Cause

Django's `S3Boto3Storage` automatically prepends the `location` setting (AWS_LOCATION) to all paths. This is by design - it allows Django to transparently work with subdirectories in S3 buckets.

## Solution

Store paths in the database **WITHOUT** the prefix, and add it only for direct boto3 S3 operations.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ FileModel.file_path (Database)                              │
│ Value: "uploads/job_description/15/file.pdf"                │
│ (NO PREFIX)                                                  │
└─────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
┌──────────────────────┐        ┌──────────────────────┐
│ default_storage ops  │        │ boto3 S3 ops         │
│ (open, url, exists)  │        │ (presigned, copy)    │
├──────────────────────┤        ├──────────────────────┤
│ Adds prefix AUTO     │        │ Use _get_s3_key()    │
│ ↓                    │        │ ↓                    │
│ media/uploads/...    │        │ media/uploads/...    │
└──────────────────────┘        └──────────────────────┘
```

### Implementation Details

#### 1. Storage Utilities (`build_storage_key`)

Added `include_prefix` parameter:

```python
# For database storage (use with FileModel.file_path)
path = build_storage_key("uploads", "tmp", "file.pdf", include_prefix=False)
# Result: "uploads/tmp/file.pdf"

# For boto3 S3 operations (presigned URLs, copy, etc.)
s3_key = build_storage_key("uploads", "tmp", "file.pdf", include_prefix=True)
# Result: "media/uploads/tmp/file.pdf"
```

#### 2. S3Utils Helper Method

Added `_get_s3_key()` to convert database paths to S3 keys:

```python
def _get_s3_key(self, file_path: str) -> str:
    """Convert file_path (no prefix) to S3 key (with prefix)."""
    prefix = get_storage_prefix()
    if prefix and not file_path.startswith(f"{prefix}/"):
        return f"{prefix}/{file_path}"
    return file_path
```

All S3Utils methods now use this helper:
- `check_file_exists(file_path)` → checks `_get_s3_key(file_path)` in S3
- `move_file(src, dst)` → moves between `_get_s3_key(src)` and `_get_s3_key(dst)`
- `delete_file(file_path)` → deletes `_get_s3_key(file_path)`
- `get_file_metadata(file_path)` → gets metadata for `_get_s3_key(file_path)`
- `generate_presigned_get_url(file_path)` → generates URL for `_get_s3_key(file_path)`

#### 3. Presigned URL Generation

Returns path WITHOUT prefix for storage:

```python
# Generate S3 key for presigned URL (includes prefix for boto3)
s3_key = build_storage_key(S3_TMP_PREFIX, file_token, file_name, include_prefix=True)
# Result: "media/uploads/tmp/uuid/file.pdf"

# Generate file_path for cache/database (without prefix for default_storage)
file_path = build_storage_key(S3_TMP_PREFIX, file_token, file_name, include_prefix=False)
# Result: "uploads/tmp/uuid/file.pdf"

return {
    "upload_url": presigned_url,
    "file_path": file_path,  # Stored in cache and later in DB
    "file_token": file_token,
}
```

#### 4. Permanent Path Generation

```python
def generate_permanent_path(self, purpose, file_name, object_id=None):
    # Always returns path WITHOUT prefix
    if object_id is not None:
        path = build_storage_key(
            S3_UPLOADS_PREFIX, purpose, str(object_id), file_name, 
            include_prefix=False  # For database storage
        )
    else:
        path = build_storage_key(
            S3_UPLOADS_PREFIX, purpose, "unrelated", str(uuid4()), file_name,
            include_prefix=False  # For database storage
        )
    return path
```

## Migration

For deployments that already have prefixed paths in the database, run:

```bash
# See what will change
python manage.py files_migrate_paths --dry-run

# Apply changes (removes prefix from file_path values)
python manage.py files_migrate_paths --apply
```

The migration:
1. Finds all `FileModel` records with `file_path` starting with the prefix
2. Verifies the S3 object exists
3. Removes the prefix from `file_path` in the database

## Verification

After migration, verify files are accessible:

```python
from apps.files.models import FileModel
from django.core.files.storage import default_storage

file = FileModel.objects.first()
print(f"file_path in DB: {file.file_path}")
# Should be: "uploads/job_description/15/file.pdf" (no prefix)

# This should work now:
with default_storage.open(file.file_path, 'rb') as f:
    data = f.read()
    print(f"Successfully read {len(data)} bytes")

# This should also work:
url = default_storage.url(file.file_path)
print(f"File URL: {url}")
# Should be valid S3 URL pointing to "media/uploads/job_description/15/file.pdf"
```

## Why This Approach is Correct

1. **Django Design**: `default_storage` is designed to add the location automatically. Fighting this design leads to bugs.

2. **Separation of Concerns**:
   - Database stores **logical paths** (application-level)
   - S3 operations use **physical keys** (infrastructure-level)
   - The `_get_s3_key()` method bridges these two

3. **Compatibility**: Works seamlessly with all Django storage operations:
   - `default_storage.open(file_path)`
   - `default_storage.url(file_path)`
   - `default_storage.exists(file_path)`
   - `default_storage.size(file_path)`
   - `default_storage.delete(file_path)`

4. **Consistency**: Other Django apps (like `django-import-export`) use the same pattern - store paths without prefix, let storage backend handle it.

## Testing

Updated all tests to reflect the new behavior:
- Presigned URL tests verify S3 key has prefix but returned path doesn't
- Permanent path tests verify paths don't include prefix
- Migration tests verify prefix removal logic

## Backward Compatibility

The `_get_s3_key()` method handles both cases:
- If path already has prefix (old data before migration): uses it as-is
- If path doesn't have prefix (new data, or migrated): adds prefix

This ensures the system works during the migration transition period.

## Summary

| Aspect | Before (Incorrect) | After (Correct) |
|--------|-------------------|----------------|
| **DB file_path** | `media/uploads/file.pdf` | `uploads/file.pdf` |
| **S3 key** | `media/uploads/file.pdf` | `media/uploads/file.pdf` |
| **default_storage behavior** | Adds prefix → `media/media/...` ❌ | Adds prefix → `media/uploads/...` ✅ |
| **File accessible?** | NO | YES |

The fix aligns with Django's storage backend design and resolves the double-prefixing issue reported by the user.
