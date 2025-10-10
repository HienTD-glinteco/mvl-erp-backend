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

# Success messages
SUCCESS_IMPORT_COMPLETE = "Import completed successfully"
SUCCESS_ROWS_IMPORTED = "{count} rows imported successfully"

# Log messages
LOG_IMPORT_STARTED = "Import started for {model} with {rows} rows"
LOG_IMPORT_COMPLETED = "Import completed for {model}: {success} success, {error} errors"
LOG_VALIDATION_ERROR = "Validation error in row {row}: {error}"
