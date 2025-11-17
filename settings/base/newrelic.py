from .base import config

NEWRELIC_ENABLED = config("NEWRELIC_ENABLED", default=False, cast=bool)
if NEWRELIC_ENABLED:
    NEWRELIC_APP_NAME = config("NEWRELIC_APP_NAME", default="MaiVietLand Backend")
    NEWRELIC_LICENSE_KEY = config("NEWRELIC_LICENSE_KEY")
    NEWRELIC_LOG_LEVEL = config("NEWRELIC_LOG_LEVEL", default="info")
