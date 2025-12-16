from django.db import models
from django.utils.translation import gettext as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class JobDescription(AutoCodeMixin, BaseModel):
    """Job description for recruitment positions"""

    CODE_PREFIX = "JD"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    code = models.CharField(max_length=50, unique=True, verbose_name="Job description code")
    title = models.CharField(max_length=200, verbose_name="Job title")
    position_title = models.CharField(max_length=255, verbose_name="Position title")
    responsibility = SafeTextField(verbose_name="Responsibility")
    requirement = SafeTextField(verbose_name="Requirement")
    preferred_criteria = SafeTextField(blank=True, verbose_name="Preferred criteria")
    benefit = SafeTextField(verbose_name="Benefit")
    proposed_salary = models.CharField(max_length=100, verbose_name="Proposed salary")
    note = SafeTextField(blank=True, verbose_name="Note")
    attachment = models.ForeignKey(
        "files.FileModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="job_descriptions",
        verbose_name="Attachment",
    )

    class Meta:
        verbose_name = _("Job Description")
        verbose_name_plural = _("Job Descriptions")
        db_table = "hrm_job_description"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"
