from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.base_model_mixin import BaseModel

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class RecruitmentChannel(BaseModel):
    """Recruitment channel for tracking candidate sources"""

    CODE_PREFIX = "CH"

    class BelongTo(models.TextChoices):
        JOB_WEBSITE = "job_website", _("Job Website")
        MARKETING = "marketing", _("Marketing")

    name = models.CharField(max_length=200, verbose_name=_("Channel name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Channel code"))
    belong_to = models.CharField(
        max_length=20,
        choices=BelongTo.choices,
        default=BelongTo.MARKETING,
        verbose_name=_("Belong to"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Recruitment Channel")
        verbose_name_plural = _("Recruitment Channels")
        db_table = "hrm_recruitment_channel"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        """Override save to set temporary code for new instances."""
        # Set temporary code for new instances that don't have a code yet
        # Use random string to avoid collisions, not all, but most of the time.
        if self._state.adding and not self.code:
            self.code = f"{TEMP_CODE_PREFIX}{get_random_string(20)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"
