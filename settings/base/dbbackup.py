from .base import config

DBBACKUP_FILENAME_TEMPLATE = config("DBBACKUP_FILENAME_TEMPLATE", default="mvl_backend-{datetime}.{extension}")
