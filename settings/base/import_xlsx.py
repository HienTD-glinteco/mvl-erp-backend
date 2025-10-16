from .base import config

# Import settings
IMPORTER_CELERY_ENABLED = config("IMPORTER_CELERY_ENABLED", default=False, cast=bool)
IMPORTER_STORAGE_BACKEND = config("IMPORTER_STORAGE_BACKEND", default="local")  # 'local' or 's3'
IMPORTER_S3_BUCKET_NAME = config("IMPORTER_S3_BUCKET_NAME", default="")
IMPORTER_S3_SIGNED_URL_EXPIRE = config("IMPORTER_S3_SIGNED_URL_EXPIRE", default=3600, cast=int)
IMPORTER_FILE_EXPIRE_DAYS = config("IMPORTER_FILE_EXPIRE_DAYS", default=7, cast=int)
IMPORTER_LOCAL_STORAGE_PATH = "imports"  # Relative to MEDIA_ROOT
IMPORTER_MAX_PREVIEW_ROWS = config("IMPORTER_MAX_PREVIEW_ROWS", default=10, cast=int)
