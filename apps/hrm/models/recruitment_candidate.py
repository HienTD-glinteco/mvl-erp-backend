from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class RecruitmentCandidate(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Candidate applying for recruitment request"""

    CODE_PREFIX = "UV"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class Status(models.TextChoices):
        CONTACTED = "CONTACTED", _("Contacted")
        INTERVIEW_SCHEDULED_1 = "INTERVIEW_SCHEDULED_1", _("Interview Scheduled 1")
        INTERVIEWED_1 = "INTERVIEWED_1", _("Interviewed 1")
        INTERVIEW_SCHEDULED_2 = "INTERVIEW_SCHEDULED_2", _("Interview Scheduled 2")
        INTERVIEWED_2 = "INTERVIEWED_2", _("Interviewed 2")
        HIRED = "HIRED", _("Hired")
        REJECTED = "REJECTED", _("Rejected")

    class YearsOfExperience(models.TextChoices):
        NO_EXPERIENCE = "NO_EXPERIENCE", _("No Experience")
        LESS_THAN_ONE_YEAR = "LESS_THAN_ONE_YEAR", _("Less Than One Year")
        ONE_TO_THREE_YEARS = "ONE_TO_THREE_YEARS", _("1-3 Years")
        THREE_TO_FIVE_YEARS = "THREE_TO_FIVE_YEARS", _("3-5 Years")
        MORE_THAN_FIVE_YEARS = "MORE_THAN_FIVE_YEARS", _("More Than 5 Years")

    VARIANT_MAPPING = {
        "status": {
            Status.CONTACTED: ColorVariant.GREY,
            Status.INTERVIEW_SCHEDULED_1: ColorVariant.YELLOW,
            Status.INTERVIEWED_1: ColorVariant.ORANGE,
            Status.INTERVIEW_SCHEDULED_2: ColorVariant.PURPLE,
            Status.INTERVIEWED_2: ColorVariant.BLUE,
            Status.HIRED: ColorVariant.GREEN,
            Status.REJECTED: ColorVariant.RED,
        }
    }

    code = models.CharField(max_length=50, unique=True, verbose_name=_("Candidate code"))
    name = models.CharField(max_length=200, verbose_name=_("Candidate name"))
    citizen_id = models.CharField(
        max_length=12,
        verbose_name=_("Citizen ID"),
        validators=[
            RegexValidator(
                regex=r"^\d{12}$",
                message=_("Citizen ID must contain exactly 12 digits."),
            )
        ],
    )
    email = models.EmailField(verbose_name=_("Email"))
    phone = models.CharField(max_length=20, verbose_name=_("Phone"))
    recruitment_request = models.ForeignKey(
        "RecruitmentRequest",
        on_delete=models.PROTECT,
        related_name="candidates",
        verbose_name=_("Recruitment request"),
    )
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="recruitment_candidates",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="recruitment_candidates",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="recruitment_candidates",
        verbose_name=_("Department"),
        null=True,
        blank=True,
    )
    recruitment_source = models.ForeignKey(
        "RecruitmentSource",
        on_delete=models.PROTECT,
        related_name="candidates",
        verbose_name=_("Recruitment source"),
    )
    recruitment_channel = models.ForeignKey(
        "RecruitmentChannel",
        on_delete=models.PROTECT,
        related_name="candidates",
        verbose_name=_("Recruitment channel"),
    )
    years_of_experience = models.CharField(
        max_length=30,
        choices=YearsOfExperience.choices,
        default=YearsOfExperience.NO_EXPERIENCE,
        verbose_name=_("Years of experience"),
    )
    submitted_date = models.DateField(verbose_name=_("Submitted date"))
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.CONTACTED,
        verbose_name=_("Status"),
    )
    onboard_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Onboard date"),
    )
    note = models.TextField(blank=True, verbose_name=_("Note"))
    referrer = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referred_candidates",
        verbose_name=_("Referrer"),
    )

    class Meta:
        verbose_name = _("Recruitment Candidate")
        verbose_name_plural = _("Recruitment Candidates")
        db_table = "hrm_recruitment_candidate"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def colored_status(self):
        """Get status with color variant"""
        return self.get_colored_value("status")

    def clean(self):
        """Validate recruitment candidate business rules"""
        super().clean()
        errors = {}

        # Validate onboard_date is required when status is HIRED
        if self.status == self.Status.HIRED and not self.onboard_date:
            errors["onboard_date"] = _("Onboard date is required when status is HIRED.")

        # Note: citizen_id format validation is handled by RegexValidator at field level

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Auto-set branch, block, and department from recruitment_request"""
        if self.recruitment_request:
            if not self.branch_id:
                self.branch = self.recruitment_request.branch
            if not self.block_id:
                self.block = self.recruitment_request.block
            if not self.department_id:
                self.department = self.recruitment_request.department

        self.clean()
        super().save(*args, **kwargs)
