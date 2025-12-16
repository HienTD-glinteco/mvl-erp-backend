from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel, SafeTextField


@audit_logging_register
class InterviewSchedule(BaseModel):
    """Interview schedule for recruitment candidates"""

    class InterviewType(models.TextChoices):
        IN_PERSON = "IN_PERSON", _("In Person")
        ONLINE = "ONLINE", _("Online")

    title = models.CharField(max_length=100, verbose_name="Title")
    recruitment_request = models.ForeignKey(
        "RecruitmentRequest",
        on_delete=models.PROTECT,
        related_name="interview_schedules",
        verbose_name="Recruitment request",
    )
    interview_type = models.CharField(
        max_length=20,
        choices=InterviewType.choices,
        default=InterviewType.IN_PERSON,
        verbose_name="Interview type",
    )
    location = models.CharField(max_length=200, verbose_name="Location")
    time = models.DateTimeField(verbose_name="Interview time")
    note = SafeTextField(blank=True, verbose_name="Note")
    interviewers = models.ManyToManyField(
        "Employee",
        related_name="interview_schedules",
        blank=True,
        verbose_name="Interviewers",
    )  # type: ignore[var-annotated]

    class Meta:
        verbose_name = _("Interview Schedule")
        verbose_name_plural = _("Interview Schedules")
        db_table = "hrm_interview_schedule"
        ordering = ["-time"]

    def __str__(self):
        return f"{self.title} - {self.time}"
