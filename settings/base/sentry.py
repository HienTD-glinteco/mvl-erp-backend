from .base import ENVIRONMENT, config

SENTRY_DSN = config("SENTRY_DSN", default="")
SENTRY_TRACES_SAMPLE_RATE = config("SENTRY_TRACES_SAMPLE_RATE", default=0.5, cast=float)
SENTRY_SAMPLE_RATE = config("SENTRY_SAMPLE_RATE", default=0.5, cast=float)
SENTRY_ENVIRONMENT = config("SENTRY_ENVIRONMENT", default=ENVIRONMENT)


if SENTRY_DSN and ENVIRONMENT != "local":
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        sample_rate=SENTRY_SAMPLE_RATE,
        # If you wish to associate users to errors (assuming you are using
        # django.contrib.auth) you may enable sending PII data.
        send_default_pii=True,
        environment=SENTRY_ENVIRONMENT,
    )
