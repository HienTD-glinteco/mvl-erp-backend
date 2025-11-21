from .aws import AWS_DB_STORAGE_BUCKET_NAME, AWS_STORAGE_BUCKET_NAME

DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# Backend for media file uploads
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
    "dbbackup": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {"bucket_name": AWS_DB_STORAGE_BUCKET_NAME, "default_acl": "private", "location": "dbbackups"},
    },
}

# Thumbnail settings
THUMBNAIL_ALIASES = {
    "": {
        "small": {"size": (100, 100), "crop": True},
        "medium": {"size": (200, 200), "crop": True},
        "large": {"size": (300, 300), "crop": True},
    },
}

THUMBNAIL_BASEDIR = "thumbnails"
THUMBNAIL_DEFAULT_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
