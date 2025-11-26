from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class Bank(BaseModel):
    """Bank model representing financial institutions.

    Attributes:
        name: Full name of the bank
        code: Unique bank code/identifier
    """

    name = models.CharField(max_length=255, verbose_name=_("Bank name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Bank code"))

    class Meta:
        verbose_name = _("Bank")
        verbose_name_plural = _("Banks")
        db_table = "hrm_bank"
        ordering = ["id"]

    def __str__(self):
        return f"{self.code} - {self.name}"
