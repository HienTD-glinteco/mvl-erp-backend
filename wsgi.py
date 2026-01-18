"""
WSGI config for backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
os.environ["AWS_REQUEST_CHECKSUM_CALCULATION"] = "when_required"
os.environ["AWS_RESPONSE_CHECKSUM_VALIDATION"] = "when_required"

# Entrypoint for share task
from celery_tasks import celery_app  # NOQA
from django.conf import settings

application = get_wsgi_application()

if getattr(settings, "NEWRELIC_ENABLED", False):
    logging.info("Initializing New Relic WSGI application wrapper")
    import newrelic.agent

    newrelic.agent.initialize()
    config = newrelic.agent.global_settings()
    config.license_key = settings.NEWRELIC_LICENSE_KEY
    config.app_name = settings.NEWRELIC_APP_NAME
    config.log_level = settings.NEWRELIC_LOG_LEVEL
    config.distributed_tracing.enabled = getattr(settings, "NEWRELIC_DISTRIBUTED_TRACING", True)
    config.error_collector.enabled = getattr(settings, "NEWRELIC_ERROR_COLLECTOR", True)

    application = newrelic.agent.wsgi_application()(application)
