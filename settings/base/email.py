from .base import config

# Email configuration
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # For development
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@maivietland.com")

# In production, you would use SMTP:
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
# EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
# EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
# EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
# EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")