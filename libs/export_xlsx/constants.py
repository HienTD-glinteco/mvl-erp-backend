"""
Constants for XLSX export module.
"""

# Fields to exclude from auto-generated schema
DEFAULT_EXCLUDED_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
    "deleted_at",
    "is_deleted",
}

# Default styling constants
DEFAULT_HEADER_FONT_SIZE = 11
DEFAULT_HEADER_FONT_BOLD = True
DEFAULT_HEADER_BG_COLOR = "D3D3D3"  # Light gray
DEFAULT_HEADER_ALIGNMENT = "center"
DEFAULT_DATA_ALIGNMENT = "left"

# Storage constants
STORAGE_LOCAL = "local"
STORAGE_S3 = "s3"

# Error messages
ERROR_INVALID_SCHEMA = "Invalid export schema"
ERROR_INVALID_STORAGE = "Invalid storage backend"
ERROR_MISSING_QUERYSET = "ViewSet must have a queryset attribute"
ERROR_MISSING_MODEL = "Cannot determine model from queryset"
