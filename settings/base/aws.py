from .base import config

# AWS common settings
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
AWS_DB_STORAGE_BUCKET_NAME = config("AWS_DB_STORAGE_BUCKET_NAME", default="")
AWS_REGION_NAME = config("AWS_REGION_NAME", default="")
AWS_S3_ENDPOINT_URL = config("AWS_S3_ENDPOINT_URL", default="s3.amazonaws.com")

# S3 settings
AWS_S3_REGION_NAME = AWS_REGION_NAME
AWS_QUERYSTRING_AUTH = False
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.{AWS_S3_ENDPOINT_URL}"
AWS_LOCATION = "media"
# AWS_S3_OBJECT_PARAMETERS = {
#     "ACL": "public-read",
# }

# OpenSearch settings (AWS-managed or self-hosted)
OPENSEARCH_HOST = config("OPENSEARCH_HOST", default="localhost")
OPENSEARCH_PORT = config("OPENSEARCH_PORT", default=9200, cast=int)
OPENSEARCH_USERNAME = config("OPENSEARCH_USERNAME", default="")
OPENSEARCH_PASSWORD = config("OPENSEARCH_PASSWORD", default="")
OPENSEARCH_USE_SSL = config("OPENSEARCH_USE_SSL", default=False, cast=bool)
OPENSEARCH_VERIFY_CERTS = config("OPENSEARCH_VERIFY_CERTS", default=False, cast=bool)
OPENSEARCH_INDEX_PREFIX = config("OPENSEARCH_INDEX_PREFIX", default="audit-logs")
