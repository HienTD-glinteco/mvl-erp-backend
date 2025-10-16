"""Constants for file management."""

# API Documentation Constants
API_PRESIGN_SUMMARY = "Generate presigned URL for file upload"
API_PRESIGN_DESCRIPTION = (
    "Generate a presigned S3 URL for direct file upload. "
    "The URL is valid for 1 hour and stored in cache for later confirmation."
)
API_PRESIGN_TAG = "Files"

API_CONFIRM_SUMMARY = "Confirm file upload"
API_CONFIRM_DESCRIPTION = (
    "Confirm a file upload by moving it from temporary storage to permanent location "
    "and creating a FileModel record linked to the related object."
)
API_CONFIRM_TAG = "Files"

# Error Messages
ERROR_INVALID_FILE_TOKEN = "Invalid or expired file token"
ERROR_FILE_NOT_FOUND_S3 = "File not found in S3"
ERROR_RELATED_MODEL_NOT_FOUND = "Related model not found"
ERROR_INVALID_PURPOSE = "Invalid file purpose"

# Cache Keys
CACHE_KEY_PREFIX = "file_upload:"
CACHE_TIMEOUT = 3600  # 1 hour

# S3 Paths
S3_TMP_PREFIX = "uploads/tmp/"
S3_UPLOADS_PREFIX = "uploads/"

# Presigned URL Settings
PRESIGNED_URL_EXPIRATION = 3600  # 1 hour

# Allowed file types per purpose
# Format: purpose -> list of allowed MIME types (None = allow all)
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
    # Add more purposes as needed
    # If a purpose is not listed here, all file types are allowed
}

# Error Messages for file type validation
ERROR_INVALID_FILE_TYPE = "Invalid file type for purpose {purpose}. Allowed types: {allowed_types}"
