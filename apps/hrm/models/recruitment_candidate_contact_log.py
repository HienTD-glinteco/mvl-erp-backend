from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class RecruitmentCandidateContactLog(BaseModel):
    """Contact history log for recruitment candidates"""

    employee = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="candidate_contact_logs",
        verbose_name=_("Employee"),
    )
    date = models.DateField(verbose_name=_("Contact date"))
    method = models.CharField(max_length=100, verbose_name=_("Contact method"))
    note = models.TextField(blank=True, verbose_name=_("Note"))
    recruitment_candidate = models.ForeignKey(
        "RecruitmentCandidate",
        on_delete=models.CASCADE,
        related_name="contact_logs",
        verbose_name=_("Recruitment candidate"),
    )

    class Meta:
        verbose_name = _("Recruitment Candidate Contact Log")
        verbose_name_plural = _("Recruitment Candidate Contact Logs")
        db_table = "hrm_recruitment_candidate_contact_log"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.recruitment_candidate.name} - {self.date} - {self.method}"
