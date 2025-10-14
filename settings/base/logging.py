import os
from typing import Any

from .base import BASE_DIR, LOG_LEVEL

LOG_DIRECTORY = os.path.join(BASE_DIR, "logs")


LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": 'timestamp="%(asctime)s" logger="%(name)s" level="%(levelname)s" msg="%(message)s"',
        },
        "default": {
            "format": 'timestamp="%(asctime)s" logger="%(name)s" level="%(levelname)s" file="%(filename)s" line=%(lineno)d msg="%(message)s"'
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
}

# Always set up audit file logging (even if AUDIT_LOG_DISABLED is True)
# File logging should always happen; AUDIT_LOG_DISABLED only controls RabbitMQ streaming
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)
if not os.path.exists(os.path.join(LOG_DIRECTORY, "audit_logging")):
    os.makedirs(os.path.join(LOG_DIRECTORY, "audit_logging"))

LOGGING["formatters"]["audit_logging"] = {
    "format": "{levelname} {asctime} {module} {message}",
    "style": "{",
}
LOGGING["handlers"]["audit_file"] = {
    "level": "INFO",
    "class": "logging.handlers.TimedRotatingFileHandler",
    "filename": os.path.join(LOG_DIRECTORY, "audit_logging", "audit.log"),
    "when": "midnight",
    "backupCount": 30,
    "utc": True,
    "formatter": "audit_logging",
}

LOGGING.setdefault("loggers", {})
LOGGING["loggers"]["audit_logging"] = {  # A dedicated logger for our audit trails
    "handlers": ["audit_file"],
    "level": "INFO",
    "propagate": False,
}
