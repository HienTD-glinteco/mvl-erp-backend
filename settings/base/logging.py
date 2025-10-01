from .base import BASE_DIR, LOG_LEVEL

LOG_DIRECTORY = BASE_DIR

LOGGING = {
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
