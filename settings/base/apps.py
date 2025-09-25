DJANGO_APPs = [
    # "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.humanize",
]

EXTERNAL_APPS = [
    "django_extensions",
    "django_filters",
    "easy_thumbnails",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_standardized_errors",
    "drf_spectacular",
    "django_celery_beat",
    "django_celery_results",
    "health_check",  # required
    "health_check.db",  # stock Django health checkers
    "health_check.cache",
    "health_check.contrib.s3boto3_storage",
    "health_check.contrib.migrations",
    "health_check.contrib.celery",  # requires celery
    "health_check.contrib.celery_ping",  # requires celery
]

INTERNAL_APPS = [
    "apps.core",
    "apps.hrm",
]

INSTALLED_APPS = DJANGO_APPs + EXTERNAL_APPS + INTERNAL_APPS
