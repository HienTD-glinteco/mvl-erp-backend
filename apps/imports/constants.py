"""Constants for the imports app."""

# Import job status choices
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

IMPORT_JOB_STATUS_CHOICES = [
    (STATUS_QUEUED, "Queued"),
    (STATUS_RUNNING, "Running"),
    (STATUS_SUCCEEDED, "Succeeded"),
    (STATUS_FAILED, "Failed"),
    (STATUS_CANCELLED, "Cancelled"),
]

# Redis key template for progress tracking
IMPORT_PROGRESS_KEY_TEMPLATE = "import:progress:{import_job_id}"

# Default progress expiration in Redis (24 hours)
REDIS_PROGRESS_EXPIRE_SECONDS = 86400

# File purposes for import results
FILE_PURPOSE_IMPORT_SUCCESS = "import_result"
FILE_PURPOSE_IMPORT_FAILED = "import_failed"
FILE_PURPOSE_IMPORT_TEMPLATE = "import_template"

# API messages
API_MESSAGE_IMPORT_STARTED = "Import started. Check status at /api/import/status/?task_id={import_job_id}"
API_MESSAGE_CANCELLED_SUCCESS = "Import job cancelled successfully"
API_MESSAGE_CANNOT_CANCEL = "Cannot cancel import job with status: {status}"

# Error messages
ERROR_FILE_NOT_FOUND = "File not found"
ERROR_FILE_NOT_CONFIRMED = "File has not been confirmed"
ERROR_MISSING_HANDLER = "Import handler not configured"
ERROR_HANDLER_NOT_FOUND = "Import handler not found: {handler_path}"
ERROR_INVALID_HANDLER = "Invalid import handler: {handler_path}"
ERROR_TASK_ID_REQUIRED = "task_id parameter is required"
ERROR_PERMISSION_DENIED = "You don't have permission to access this import job"
ERROR_NO_TEMPLATE = "No import template available for this resource"
ERROR_INVALID_OPTION_KEY = "Invalid option key: {key}. Allowed keys: {allowed_keys}"

# Import options validation
ALLOWED_OPTION_KEYS = {
    "batch_size",
    "count_total_first",
    "header_rows",
    "output_format",
    "create_result_file_records",
    "handler_path",
    "handler_options",
    "result_file_prefix",
}

# Import option defaults and constraints
DEFAULT_BATCH_SIZE = 500
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 100000

DEFAULT_COUNT_TOTAL_FIRST = True
DEFAULT_HEADER_ROWS = 1
MIN_HEADER_ROWS = 0
MAX_HEADER_ROWS = 100

DEFAULT_OUTPUT_FORMAT = "csv"
ALLOWED_OUTPUT_FORMATS = ["csv", "xlsx"]

DEFAULT_CREATE_RESULT_FILE_RECORDS = True
