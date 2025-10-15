from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class RecruitmentSource(AutoCodeMixin, BaseModel):
    """Recruitment source for tracking where candidates come from"""

    CODE_PREFIX = "RS"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    name = models.CharField(max_length=200, verbose_name=_("Source name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Source code"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Recruitment Source")
        verbose_name_plural = _("Recruitment Sources")
        db_table = "hrm_recruitment_source"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"
