from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class RecruitmentRequest(AutoCodeMixin, BaseModel):
    """Recruitment request for new hire or replacement positions"""

    CODE_PREFIX = "RR"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class RecruitmentType(models.TextChoices):
        NEW_HIRE = "NEW_HIRE", _("New Hire")
        REPLACEMENT = "REPLACEMENT", _("Replacement")

    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        OPEN = "OPEN", _("Open")
        PAUSED = "PAUSED", _("Paused")
        CLOSED = "CLOSED", _("Closed")

    code = models.CharField(max_length=50, unique=True, verbose_name=_("Request code"))
    name = models.CharField(max_length=200, verbose_name=_("Request name"))
    job_description = models.ForeignKey(
        "JobDescription",
        on_delete=models.PROTECT,
        related_name="recruitment_requests",
        verbose_name=_("Job description"),
    )
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="recruitment_requests",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="recruitment_requests",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="recruitment_requests",
        verbose_name=_("Department"),
        null=True,
        blank=True,
    )
    proposer = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="proposed_recruitment_requests",
        verbose_name=_("Proposer"),
    )
    recruitment_type = models.CharField(
        max_length=20,
        choices=RecruitmentType.choices,
        verbose_name=_("Recruitment type"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("Status"),
    )
    proposed_salary = models.CharField(max_length=100, verbose_name=_("Proposed salary"))
    number_of_positions = models.IntegerField(default=1, verbose_name=_("Number of positions"))

    class Meta:
        verbose_name = _("Recruitment Request")
        verbose_name_plural = _("Recruitment Requests")
        db_table = "hrm_recruitment_request"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        """Validate recruitment request"""
        super().clean()
        errors = {}

        # Validate organizational hierarchy
        if self.department and self.block:
            if self.department.block_id != self.block_id:
                errors["department"] = _("Department must belong to the selected block.")

        if self.department and self.branch:
            if self.department.branch_id != self.branch_id:
                errors["department"] = _("Department must belong to the selected branch.")

        if self.block and self.branch:
            if self.block.branch_id != self.branch_id:
                errors["block"] = _("Block must belong to the selected branch.")

        # Validate number of positions
        if hasattr(self, "number_of_positions") and self.number_of_positions < 1:
            errors["number_of_positions"] = _("Number of positions must be at least 1.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Auto-set branch and block from department"""
        if self.department:
            if not self.branch_id:
                self.branch = self.department.branch
            if not self.block_id:
                self.block = self.department.block

        self.clean()
        super().save(*args, **kwargs)
