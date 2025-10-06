from .base import config

# Audit logging settings
AUDIT_LOG_DISABLED = config("AUDIT_LOG_DISABLED", cast=bool, default=False)
