from .base import config

# Export settings
EXPORTER_CELERY_ENABLED = config("EXPORTER_CELERY_ENABLED", default=False, cast=bool)
EXPORTER_STORAGE_BACKEND = config("EXPORTER_STORAGE_BACKEND", default="local")  # 'local' or 's3'
EXPORTER_S3_BUCKET_NAME = config("EXPORTER_S3_BUCKET_NAME", default="")
EXPORTER_S3_SIGNED_URL_EXPIRE = config("EXPORTER_S3_SIGNED_URL_EXPIRE", default=3600, cast=int)
EXPORTER_FILE_EXPIRE_DAYS = config("EXPORTER_FILE_EXPIRE_DAYS", default=7, cast=int)
EXPORTER_LOCAL_STORAGE_PATH = "exports"  # Relative to MEDIA_ROOT
