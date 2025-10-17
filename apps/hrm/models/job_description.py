from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class JobDescription(AutoCodeMixin, BaseModel):
    """Job description for recruitment positions"""

    CODE_PREFIX = "JD"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    code = models.CharField(max_length=50, unique=True, verbose_name=_("Job description code"))
    title = models.CharField(max_length=200, verbose_name=_("Job title"))
    responsibility = SafeTextField(verbose_name=_("Responsibility"))
    requirement = SafeTextField(verbose_name=_("Requirement"))
    preferred_criteria = SafeTextField(blank=True, verbose_name=_("Preferred criteria"))
    benefit = SafeTextField(verbose_name=_("Benefit"))
    proposed_salary = models.CharField(max_length=100, verbose_name=_("Proposed salary"))
    note = SafeTextField(blank=True, verbose_name=_("Note"))
    attachment = models.CharField(max_length=500, blank=True, verbose_name=_("Attachment"))

    class Meta:
        verbose_name = _("Job Description")
        verbose_name_plural = _("Job Descriptions")
        db_table = "hrm_job_description"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"
