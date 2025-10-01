from .base import config

AUDIT_LOG_AWS_S3_BUCKET = config(
    "AUDIT_LOG_AWS_S3_BUCKET", default="backend-audit-logs"
)
AUDIT_LOG_BATCH_SIZE = config("AUDIT_LOG_BATCH_SIZE", default=1000, cast=int)
AUDIT_LOG_FLUSH_INTERVAL = config("AUDIT_LOG_FLUSH_INTERVAL", default=60, cast=int)
