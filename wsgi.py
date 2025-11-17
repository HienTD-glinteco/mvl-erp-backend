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

# Entrypoint for share task
from celery_tasks import celery_app  # NOQA
from django.conf import settings

application = get_wsgi_application()

if getattr(settings, "NEWRELIC_ENABLED", False):
    logging.info("Initializing New Relic WSGI application wrapper")
    import newrelic.agent

    newrelic.agent.initialize(
        config_file=None,
        environment=None,
        ignore_errors=[],
        log_file=None,
        log_level=settings.NEWRELIC_LOG_LEVEL,
    )
    application = newrelic.agent.wsgi_application()(application)
