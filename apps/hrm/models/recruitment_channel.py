from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class RecruitmentChannel(AutoCodeMixin, BaseModel):
    """Recruitment channel for tracking candidate sources"""

    CODE_PREFIX = "CH"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class BelongTo(models.TextChoices):
        JOB_WEBSITE = "job_website", _("Job Website")
        MARKETING = "marketing", _("Marketing")
        HUNT = "hunt", _("Hunt")
        SCHOOL = "school", _("School")

    name = models.CharField(max_length=200, verbose_name=_("Channel name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Channel code"))
    belong_to = models.CharField(
        max_length=20,
        choices=BelongTo.choices,
        blank=True,
        default="",
        verbose_name=_("Belong to"),
    )
    description = SafeTextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Recruitment Channel")
        verbose_name_plural = _("Recruitment Channels")
        db_table = "hrm_recruitment_channel"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"
