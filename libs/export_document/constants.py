"""
Constants for document export functionality.
"""

# File type constants
FILE_TYPE_PDF = "pdf"
FILE_TYPE_DOCX = "docx"

# Delivery mode constants
DELIVERY_DIRECT = "direct"
DELIVERY_LINK = "link"

# Default values
DEFAULT_FILE_TYPE = FILE_TYPE_PDF
DEFAULT_DELIVERY = DELIVERY_DIRECT

# Error messages
ERROR_INVALID_FILE_TYPE = "Invalid file type. Allowed: pdf, docx"
ERROR_INVALID_DELIVERY = "Invalid delivery parameter. Allowed: link, direct"
ERROR_TEMPLATE_MISSING = "Document template name not specified"
ERROR_CONVERSION_FAILED = "Failed to convert HTML to document"
ERROR_S3_UPLOAD_FAILED = "Failed to upload file to S3"

# Storage backend
STORAGE_S3 = "s3"
STORAGE_LOCAL = "local"
