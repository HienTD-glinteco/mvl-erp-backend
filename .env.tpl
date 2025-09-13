# COMMON
DEBUG=true
LOG_LEVEL=ERROR
SECRET_KEY=YOUR_SECRET_KEY
DATABASE_URL=postgres://backend:password@localhost:5432/backend
ALLOWED_HOSTS=localhost,127.0.0.1  # a list of hosts seperated by commas
CSRF_TRUSTED_ORIGINS=  # A list of trusted origins for unsafe requests seperated by commas. Ref: https://docs.djangoproject.com/en/5.1/ref/settings/#csrf-trusted-origins
CORS_ALLOWED_ORIGINS=  # Ref: https://github.com/adamchainz/django-cors-headers?tab=readme-ov-file#cors_allowed_origins-sequencestr
CORS_ALLOWED_ORIGIN_REGEXES=  # Ref: https://github.com/adamchainz/django-cors-headers?tab=readme-ov-file#cors_allowed_origin_regexes-sequencestr--patternstr

ACCESS_TOKEN_LIFETIME=86400  # seconds. 1 day
REFRESH_TOKEN_LIFETIME=2592000  # seconds. 30 days

# SENTRY
SENTRY_DSN=YOUR_SENTRY_DSN
SENTRY_ENVIRONMENT=prod  #  one of: prod, staging
SENTRY_TRACES_SAMPLE_RATE=0.3
SENTRY_SAMPLE_RATE=0.5

# CELERY
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_TASK_ALWAYS_EAGER=True
CELERY_TASK_EAGER_PROPAGATES=True

# CACHE
CACHE_URL=redis://localhost:6379/0
CACHE_PREFIX=
CACHE_TIMEOUT=2592000

# AWS
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_REGION_NAME=
AWS_STORAGE_BUCKET_NAME=
