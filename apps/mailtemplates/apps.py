from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MailTemplatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mailtemplates"
    verbose_name = _("Mail Templates")
