from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class ContractType(BaseModel):
    """Contract type model representing employment contract types."""

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Contract type name"),
    )

    class Meta:
        verbose_name = _("Contract type")
        verbose_name_plural = _("Contract types")
        db_table = "hrm_contract_type"
        ordering = ["name"]

    def __str__(self):
        return self.name
