from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class InterviewCandidate(BaseModel):
    """Link table between interview schedule and recruitment candidate"""

    recruitment_candidate = models.ForeignKey(
        "RecruitmentCandidate",
        on_delete=models.CASCADE,
        related_name="interview_candidates",
        verbose_name=_("Recruitment candidate"),
    )
    interview_schedule = models.ForeignKey(
        "InterviewSchedule",
        on_delete=models.CASCADE,
        related_name="interview_candidates",
        verbose_name=_("Interview schedule"),
    )
    interview_time = models.DateTimeField(verbose_name=_("Interview time"))
    email_sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Email sent at"))

    class Meta:
        verbose_name = _("Interview Candidate")
        verbose_name_plural = _("Interview Candidates")
        db_table = "hrm_interview_candidate"
        unique_together = [["recruitment_candidate", "interview_schedule"]]
        ordering = ["interview_time"]

    def __str__(self):
        return f"{self.recruitment_candidate.name} - {self.interview_schedule.title}"
