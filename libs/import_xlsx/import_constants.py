"""
Constants for XLSX import functionality.
"""

# Import status
IMPORT_STATUS_PENDING = "PENDING"
IMPORT_STATUS_PROCESSING = "PROCESSING"
IMPORT_STATUS_SUCCESS = "SUCCESS"
IMPORT_STATUS_FAILED = "FAILED"

# Field types to ignore in auto schema generation
IGNORED_FIELD_NAMES = {"id", "created_at", "updated_at", "deleted_at"}
IGNORED_FIELD_TYPES = {"AutoField", "BigAutoField", "DateTimeField"}

# Import action metadata
IMPORT_ACTION_NAME = "Import {model_name}"
IMPORT_ACTION_DESCRIPTION = "Import {model_name} from XLSX file"

# Error messages
ERROR_NO_FILE = "No file provided"
ERROR_INVALID_FILE_TYPE = "Invalid file type. Only .xlsx files are supported"
ERROR_EMPTY_FILE = "File is empty or has no data"
ERROR_MISSING_COLUMNS = "Missing required columns: {columns}"
ERROR_INVALID_DATA = "Invalid data in row {row}: {error}"
ERROR_DUPLICATE_KEY = "Duplicate key in row {row}: {key}"
ERROR_ASYNC_NOT_ENABLED = "Async import is not enabled"
ERROR_FOREIGN_KEY_NOT_FOUND = "Related object not found for {field}: {value}"

# Success messages
SUCCESS_IMPORT_COMPLETE = "Import completed successfully"
SUCCESS_ROWS_IMPORTED = "{count} rows imported successfully"
SUCCESS_PREVIEW_COMPLETE = "Preview completed successfully"

# Log messages
LOG_IMPORT_STARTED = "Import started for {model} with {rows} rows"
LOG_IMPORT_COMPLETED = "Import completed for {model}: {success} success, {error} errors"
LOG_VALIDATION_ERROR = "Validation error in row {row}: {error}"

# Storage constants
STORAGE_LOCAL = "local"
STORAGE_S3 = "s3"

# Configuration errors
ERROR_INVALID_CONFIG = "Invalid import configuration"
ERROR_MISSING_SHEETS = "Configuration must have 'sheets' key"
ERROR_INVALID_SHEET = "Invalid sheet configuration"
ERROR_MISSING_MODEL = "Sheet configuration must specify 'model'"
ERROR_MODEL_NOT_FOUND = "Model '{model}' not found in Django apps"
ERROR_INVALID_FIELD_CONFIG = "Invalid field configuration for '{field}'"
ERROR_MISSING_COMBINE_FIELDS = "Field '{field}' specifies 'combine' but missing field list"
ERROR_INVALID_RELATION_CONFIG = "Invalid relation configuration for '{relation}'"

# Transformation errors
ERROR_COMBINE_MISSING_VALUE = "Missing value for combine field: {field}"
ERROR_INVALID_DATE_FORMAT = "Invalid date format for field '{field}': {value}"
ERROR_TRANSFORMATION_FAILED = "Transformation failed for field '{field}': {error}"

# Relationship errors
ERROR_PARENT_NOT_FOUND = "Parent object not found for '{model}': {value}"
ERROR_RELATED_CREATE_FAILED = "Failed to create related object '{model}': {error}"
