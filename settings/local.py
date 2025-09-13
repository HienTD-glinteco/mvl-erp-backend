"""
This configuration file overrides some necessary configs
to easily develop the app.
"""

from .base import *  # noqa

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ["127.0.0.1"]

CELERY_TASK_ALWAYS_EAGER = True
