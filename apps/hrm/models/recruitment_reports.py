from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseReportModel

from ..constants import RecruitmentSourceType
from .organization import Block, Branch, Department


class BaseReportDepartmentModel(BaseReportModel):
    """Base model for reports with organizational unit structure.

    Extends BaseReportModel with organizational fields (branch, block, department)
    and enforces unique constraint on report_date + organizational units.
    """

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="%(class)s_reports",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        Block,
        on_delete=models.CASCADE,
        related_name="%(class)s_reports",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
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

    month_key = models.CharField(
        max_length=7,
        verbose_name=_("Month key"),
        help_text=_("Format: MM/YYYY for monthly aggregation"),
        db_index=True,
    )
    week_key = models.CharField(
        max_length=20,
        verbose_name=_("Week key"),
        help_text=_("Format: Week W - MM/YYYY for weekly aggregation"),
        db_index=True,
        null=True,
        blank=True,
    )
    num_introductions = models.PositiveIntegerField(default=0, verbose_name=_("Number of introductions"))
    num_returns = models.PositiveIntegerField(default=0, verbose_name=_("Number of returns"))
    num_recruitment_source = models.PositiveIntegerField(default=0, verbose_name=_("Number of new recruitment source"))
    num_transfers = models.PositiveIntegerField(default=0, verbose_name=_("Number of transfers"))
    num_resignations = models.PositiveIntegerField(default=0, verbose_name=_("Number of resignations"))

    class Meta:
        verbose_name = _("Staff Growth Report")
        verbose_name_plural = _("Staff Growth Reports")

    def __str__(self):
        return f"Staff Growth Report - {self.report_date}"


class RecruitmentSourceReport(BaseReportDepartmentModel):
    """Daily hire statistics by recruitment source.

    Stores daily hire counts for each recruitment source within an organizational unit.
    Data is aggregated by API views to provide weekly/monthly reports with sources
    as columns and organizational units as rows.
    """

    recruitment_source = models.ForeignKey(
        "RecruitmentSource",
        on_delete=models.CASCADE,
        related_name="source_reports",
        verbose_name=_("Recruitment source"),
    )
    num_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of hires"))

    class Meta:
        verbose_name = _("Recruitment Source Report")
        verbose_name_plural = _("Recruitment Source Reports")

    def __str__(self):
        return f"Source Report - {self.recruitment_source.name} - {self.report_date}"


class RecruitmentChannelReport(BaseReportDepartmentModel):
    """Daily hire statistics by recruitment channel.

    Stores hire statistics organized by channel with organizational structure:
    branch > block > department. Each record represents data for one day.
    """

    recruitment_channel = models.ForeignKey(
        "RecruitmentChannel",
        on_delete=models.CASCADE,
        related_name="channel_reports",
        verbose_name=_("Recruitment channel"),
    )
    num_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of hires"))

    class Meta:
        verbose_name = _("Recruitment Channel Report")
        verbose_name_plural = _("Recruitment Channel Reports")

    def __str__(self):
        return f"Channel Report - {self.recruitment_channel.name} - {self.report_date}"


class RecruitmentCostReport(BaseReportDepartmentModel):
    """Daily recruitment cost data by source type.

    Stores daily cost metrics for each recruitment source type within an organizational unit.
    Source types are categorized based on recruitment source/channel flags.
    1. referral_source: recruitment sources with allow_referral=True
    2. marketing_channel: recruitment channels with belong_to='marketing'
    3. job_website_channel: recruitment channels with belong_to='job_website'
    4. recruitment_department_source: recruitment sources with allow_referral=False
    5. returning_employee: former employees returning to the company

    Note: recruitment_department_source and returning_employee have no cost, only count.
    Data is aggregated by API views to provide weekly/monthly cost reports.
    """

    source_type = models.CharField(
        max_length=50,
        choices=RecruitmentSourceType.choices,
        verbose_name=_("Source type"),
    )
    month_key = models.CharField(
        max_length=7,
        verbose_name=_("Month key"),
        help_text=_("Format: YYYY-MM for monthly aggregation"),
        db_index=True,
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

    def __str__(self):
        return f"Cost Report - {self.source_type} - {self.report_date}"


class HiredCandidateReport(BaseReportDepartmentModel):
    """Statistics of candidates who accepted offers.

    Stores hire statistics separated by source types based on recruitment source/channel flags:
    1. referral_source: recruitment sources with allow_referral=True
    2. marketing_channel: recruitment channels with belong_to='marketing'
    3. job_website_channel: recruitment channels with belong_to='job_website'
    4. recruitment_department_source: recruitment sources with allow_referral=False
    5. returning_employee: former employees returning to the company

    Each record represents data for one day.
    """

    source_type = models.CharField(
        max_length=50,
        choices=RecruitmentSourceType.choices,
        verbose_name=_("Source type"),
    )
    month_key = models.CharField(
        max_length=7,
        verbose_name=_("Month key"),
        help_text=_("Format: MM/YYYY for monthly aggregation"),
        db_index=True,
    )
    week_key = models.CharField(
        max_length=20,
        verbose_name=_("Week key"),
        help_text=_("Format: Week W - MM/YYYY for weekly aggregation"),
        db_index=True,
        null=True,
        blank=True,
    )
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="hired_candidate_reports",
        verbose_name=_("Employee"),
        null=True,
        blank=True,
        help_text=_("Only applicable for 'referral_source' type"),
    )
    num_candidates_hired = models.PositiveIntegerField(default=0, verbose_name=_("Number of candidates hired"))
    num_experienced = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Number of experienced candidates"),
        help_text=_("Candidates with prior work experience"),
    )

    class Meta:
        verbose_name = _("Hired Candidate Report")
        verbose_name_plural = _("Hired Candidate Reports")

    def __str__(self):
        return f"Hired Candidate Report - {self.source_type} - {self.report_date}"
