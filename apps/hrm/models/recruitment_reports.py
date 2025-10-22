from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel


class BaseReportModel(BaseModel):
    """Base model for all report models.

    Provides common fields and behavior for report models including
    report_date and standard ordering by report_date descending.
    """

    report_date = models.DateField(verbose_name=_("Report date"))

    class Meta:
        abstract = True
        ordering = ["-report_date"]


class BaseReportDepartmentModel(BaseReportModel):
    """Base model for reports with organizational unit structure.

    Extends BaseReportModel with organizational fields (branch, block, department)
    and enforces unique constraint on report_date + organizational units.
    """

    branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="%(class)s_reports",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="%(class)s_reports",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="%(class)s_reports",
        verbose_name=_("Department"),
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True
        unique_together = [["report_date", "branch", "block", "department"]]


class StaffGrowthReport(BaseReportDepartmentModel):
    """Daily staff growth statistics report.

    Stores data about staff changes including introductions, returns,
    new hires, transfers, and resignations for a specific date and organizational unit.
    Each record represents data for one day.
    """

    num_introductions = models.PositiveIntegerField(default=0, verbose_name=_("Number of introductions"))
    num_returns = models.PositiveIntegerField(default=0, verbose_name=_("Number of returns"))
    num_new_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of new hires"))
    num_transfers = models.PositiveIntegerField(default=0, verbose_name=_("Number of transfers"))
    num_resignations = models.PositiveIntegerField(default=0, verbose_name=_("Number of resignations"))

    class Meta:
        verbose_name = _("Staff Growth Report")
        verbose_name_plural = _("Staff Growth Reports")
        db_table = "hrm_staff_growth_report"

    def __str__(self):
        return f"Staff Growth Report - {self.report_date}"


class RecruitmentSourceReport(BaseReportDepartmentModel):
    """Daily hire statistics by recruitment source.

    Stores hire statistics organized by source with organizational structure:
    branch > block > department. Each record represents data for one day.
    """

    recruitment_source = models.ForeignKey(
        "RecruitmentSource",
        on_delete=models.PROTECT,
        related_name="source_reports",
        verbose_name=_("Recruitment source"),
    )
    num_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of hires"))

    class Meta:
        verbose_name = _("Recruitment Source Report")
        verbose_name_plural = _("Recruitment Source Reports")
        db_table = "hrm_recruitment_source_report"

    def __str__(self):
        return f"Source Report - {self.recruitment_source.name} - {self.report_date}"


class RecruitmentChannelReport(BaseReportDepartmentModel):
    """Daily hire statistics by recruitment channel.

    Stores hire statistics organized by channel with organizational structure:
    branch > block > department. Each record represents data for one day.
    """

    recruitment_channel = models.ForeignKey(
        "RecruitmentChannel",
        on_delete=models.PROTECT,
        related_name="channel_reports",
        verbose_name=_("Recruitment channel"),
    )
    num_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of hires"))

    class Meta:
        verbose_name = _("Recruitment Channel Report")
        verbose_name_plural = _("Recruitment Channel Reports")
        db_table = "hrm_recruitment_channel_report"

    def __str__(self):
        return f"Channel Report - {self.recruitment_channel.name} - {self.report_date}"


class RecruitmentCostReport(BaseReportDepartmentModel):
    """Daily cost data per source/channel with cost metrics.

    Stores recruitment cost statistics including total cost, count, and average
    cost per hire for a specific source/channel and organizational unit.
    Each record represents data for one day.
    """

    recruitment_source = models.ForeignKey(
        "RecruitmentSource",
        on_delete=models.PROTECT,
        related_name="cost_reports",
        verbose_name=_("Recruitment source"),
        null=True,
        blank=True,
    )
    recruitment_channel = models.ForeignKey(
        "RecruitmentChannel",
        on_delete=models.PROTECT,
        related_name="cost_reports",
        verbose_name=_("Recruitment channel"),
        null=True,
        blank=True,
    )
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Total cost"),
    )
    num_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of hires"))
    avg_cost_per_hire = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Average cost per hire"),
    )

    class Meta:
        verbose_name = _("Recruitment Cost Report")
        verbose_name_plural = _("Recruitment Cost Reports")
        db_table = "hrm_recruitment_cost_report"

    def __str__(self):
        source_or_channel = self.recruitment_source or self.recruitment_channel
        return f"Cost Report - {source_or_channel} - {self.report_date}"


class HiredCandidateReport(BaseReportDepartmentModel):
    """Statistics of candidates who accepted offers.

    Stores hire statistics separated by source types based on recruitment source/channel flags:
    1. referral_source: recruitment sources with allow_referral=True
    2. marketing_channel: recruitment channels with belong_to='marketing'
    3. job_website_channel: recruitment channels with belong_to='job_website'
    4. recruitment_department_source: recruitment sources with allow_referral=False
    5. returning_employee: former employees returning to the company

    Note: recruitment_department_source and returning_employee have no cost, only count.
    Each record represents data for one day.
    """

    class SourceType(models.TextChoices):
        REFERRAL_SOURCE = "referral_source", _("Referral Source")
        MARKETING_CHANNEL = "marketing_channel", _("Marketing Channel")
        JOB_WEBSITE_CHANNEL = "job_website_channel", _("Job Website Channel")
        RECRUITMENT_DEPARTMENT_SOURCE = "recruitment_department_source", _("Recruitment Department Source")
        RETURNING_EMPLOYEE = "returning_employee", _("Returning Employee")

    source_type = models.CharField(
        max_length=50,
        choices=SourceType.choices,
        verbose_name=_("Source type"),
    )
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="hired_candidate_reports",
        verbose_name=_("Employee"),
        null=True,
        blank=True,
        help_text=_("Only applicable for 'referral_source' type"),
    )
    num_candidates_hired = models.PositiveIntegerField(default=0, verbose_name=_("Number of candidates hired"))

    class Meta:
        verbose_name = _("Hired Candidate Report")
        verbose_name_plural = _("Hired Candidate Reports")
        db_table = "hrm_hired_candidate_report"

    def __str__(self):
        return f"Hired Candidate Report - {self.source_type} - {self.report_date}"
