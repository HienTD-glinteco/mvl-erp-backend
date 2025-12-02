from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class RecruitmentSource(AutoCodeMixin, BaseModel):
    """Recruitment source for tracking where candidates come from"""

    CODE_PREFIX = "RS"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    name = models.CharField(max_length=250, verbose_name="Source name")
    code = models.CharField(max_length=50, unique=True, verbose_name="Source code")
    description = SafeTextField(blank=True, verbose_name="Description", max_length=500)
    allow_referral = models.BooleanField(
        default=False,
        verbose_name="Allow referral",
        help_text="Enable users to set referrer and referee for candidates from this source",
    )

    class Meta:
        verbose_name = "Recruitment Source"
        verbose_name_plural = "Recruitment Sources"
        db_table = "hrm_recruitment_source"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"
