from .base import config

# Import settings
IMPORT_DEFAULT_BATCH_SIZE = config("IMPORT_DEFAULT_BATCH_SIZE", default=500, cast=int)
IMPORT_PROGRESS_DB_FLUSH_EVERY_N_BATCHES = config("IMPORT_PROGRESS_DB_FLUSH_EVERY_N_BATCHES", default=5, cast=int)
IMPORT_TEMP_DIR = config("IMPORT_TEMP_DIR", default=None)  # None = use system temp
IMPORT_RESULT_PRESIGN_EXPIRES = config("IMPORT_RESULT_PRESIGN_EXPIRES", default=3600, cast=int)
IMPORT_S3_PREFIX = config("IMPORT_S3_PREFIX", default="uploads/imports/")
IMPORT_ENABLE_RESULT_FILES = config("IMPORT_ENABLE_RESULT_FILES", default=True, cast=bool)
