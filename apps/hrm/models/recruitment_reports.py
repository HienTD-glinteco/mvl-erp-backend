from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class StaffGrowthReport(BaseModel):
    """Daily/weekly/monthly staff growth statistics report.
    
    Stores data about staff changes including introductions, returns,
    new hires, transfers, and resignations for a specific date and organizational unit.
    """

    report_date = models.DateField(verbose_name=_("Report date"))
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("daily", _("Daily")),
            ("weekly", _("Weekly")),
            ("monthly", _("Monthly")),
        ],
        default="daily",
        verbose_name=_("Period type"),
    )
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="staff_growth_reports",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="staff_growth_reports",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="staff_growth_reports",
        verbose_name=_("Department"),
        null=True,
        blank=True,
    )
    num_introductions = models.PositiveIntegerField(default=0, verbose_name=_("Number of introductions"))
    num_returns = models.PositiveIntegerField(default=0, verbose_name=_("Number of returns"))
    num_new_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of new hires"))
    num_transfers = models.PositiveIntegerField(default=0, verbose_name=_("Number of transfers"))
    num_resignations = models.PositiveIntegerField(default=0, verbose_name=_("Number of resignations"))

    class Meta:
        verbose_name = _("Staff Growth Report")
        verbose_name_plural = _("Staff Growth Reports")
        db_table = "hrm_staff_growth_report"
        ordering = ["-report_date"]
        unique_together = [["report_date", "period_type", "branch", "block", "department"]]

    def __str__(self):
        return f"Staff Growth Report - {self.report_date} ({self.period_type})"


@audit_logging_register
class RecruitmentSourceReport(BaseModel):
    """Nested hire statistics by recruitment source.
    
    Stores hire statistics organized by source with nested organizational structure:
    branch > block > department. Structure allows sources as columns with nested org units as rows.
    """

    report_date = models.DateField(verbose_name=_("Report date"))
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("daily", _("Daily")),
            ("weekly", _("Weekly")),
            ("monthly", _("Monthly")),
        ],
        default="monthly",
        verbose_name=_("Period type"),
    )
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="recruitment_source_reports",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="recruitment_source_reports",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="recruitment_source_reports",
        verbose_name=_("Department"),
        null=True,
        blank=True,
    )
    recruitment_source = models.ForeignKey(
        "RecruitmentSource",
        on_delete=models.PROTECT,
        related_name="source_reports",
        verbose_name=_("Recruitment source"),
    )
    org_unit_name = models.CharField(max_length=200, verbose_name=_("Organization unit name"))
    org_unit_type = models.CharField(
        max_length=20,
        choices=[
            ("branch", _("Branch")),
            ("block", _("Block")),
            ("department", _("Department")),
        ],
        verbose_name=_("Organization unit type"),
    )
    num_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of hires"))

    class Meta:
        verbose_name = _("Recruitment Source Report")
        verbose_name_plural = _("Recruitment Source Reports")
        db_table = "hrm_recruitment_source_report"
        ordering = ["-report_date"]

    def __str__(self):
        return f"Source Report - {self.recruitment_source.name} - {self.report_date}"


@audit_logging_register
class RecruitmentChannelReport(BaseModel):
    """Nested hire statistics by recruitment channel.
    
    Stores hire statistics organized by channel with nested organizational structure:
    branch > block > department. Structure allows channels as columns with nested org units as rows.
    """

    report_date = models.DateField(verbose_name=_("Report date"))
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("daily", _("Daily")),
            ("weekly", _("Weekly")),
            ("monthly", _("Monthly")),
        ],
        default="monthly",
        verbose_name=_("Period type"),
    )
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="recruitment_channel_reports",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="recruitment_channel_reports",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="recruitment_channel_reports",
        verbose_name=_("Department"),
        null=True,
        blank=True,
    )
    recruitment_channel = models.ForeignKey(
        "RecruitmentChannel",
        on_delete=models.PROTECT,
        related_name="channel_reports",
        verbose_name=_("Recruitment channel"),
    )
    org_unit_name = models.CharField(max_length=200, verbose_name=_("Organization unit name"))
    org_unit_type = models.CharField(
        max_length=20,
        choices=[
            ("branch", _("Branch")),
            ("block", _("Block")),
            ("department", _("Department")),
        ],
        verbose_name=_("Organization unit type"),
    )
    num_hires = models.PositiveIntegerField(default=0, verbose_name=_("Number of hires"))

    class Meta:
        verbose_name = _("Recruitment Channel Report")
        verbose_name_plural = _("Recruitment Channel Reports")
        db_table = "hrm_recruitment_channel_report"
        ordering = ["-report_date"]

    def __str__(self):
        return f"Channel Report - {self.recruitment_channel.name} - {self.report_date}"


@audit_logging_register
class RecruitmentCostReport(BaseModel):
    """Flat cost data per source/channel with cost metrics.
    
    Stores recruitment cost statistics including total cost, count, and average
    cost per hire for a specific source/channel and organizational unit.
    """

    report_date = models.DateField(verbose_name=_("Report date"))
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("daily", _("Daily")),
            ("weekly", _("Weekly")),
            ("monthly", _("Monthly")),
        ],
        default="monthly",
        verbose_name=_("Period type"),
    )
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="recruitment_cost_reports",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="recruitment_cost_reports",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="recruitment_cost_reports",
        verbose_name=_("Department"),
        null=True,
        blank=True,
    )
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
        ordering = ["-report_date"]

    def __str__(self):
        source_or_channel = self.recruitment_source or self.recruitment_channel
        return f"Cost Report - {source_or_channel} - {self.report_date}"


@audit_logging_register
class HiredCandidateReport(BaseModel):
    """Statistics of candidates who accepted offers.
    
    Stores hire statistics separated by 3 sources: introduction, recruitment, return.
    For 'introduction' source, includes employee-level details. For others, only summary stats.
    """

    report_date = models.DateField(verbose_name=_("Report date"))
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("weekly", _("Weekly")),
            ("monthly", _("Monthly")),
        ],
        default="monthly",
        verbose_name=_("Period type"),
    )
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="hired_candidate_reports",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="hired_candidate_reports",
        verbose_name=_("Block"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="hired_candidate_reports",
        verbose_name=_("Department"),
        null=True,
        blank=True,
    )
    source_type = models.CharField(
        max_length=20,
        choices=[
            ("introduction", _("Introduction")),
            ("recruitment", _("Recruitment")),
            ("return", _("Return")),
        ],
        verbose_name=_("Source type"),
    )
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="hired_candidate_reports",
        verbose_name=_("Employee"),
        null=True,
        blank=True,
        help_text=_("Only applicable for 'introduction' source type"),
    )
    num_candidates_hired = models.PositiveIntegerField(default=0, verbose_name=_("Number of candidates hired"))

    class Meta:
        verbose_name = _("Hired Candidate Report")
        verbose_name_plural = _("Hired Candidate Reports")
        db_table = "hrm_hired_candidate_report"
        ordering = ["-report_date"]

    def __str__(self):
        return f"Hired Candidate Report - {self.source_type} - {self.report_date}"


@audit_logging_register
class ReferralCostReport(BaseModel):
    """Referral cost summary and detail data.
    
    Stores summary and detailed breakdown of referral costs by department and employee.
    Includes both summary totals and per-employee breakdown.
    """

    report_date = models.DateField(verbose_name=_("Report date"))
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("weekly", _("Weekly")),
            ("monthly", _("Monthly")),
        ],
        default="monthly",
        verbose_name=_("Period type"),
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="referral_cost_reports",
        verbose_name=_("Department"),
    )
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="referral_cost_reports",
        verbose_name=_("Employee"),
        null=True,
        blank=True,
        help_text=_("Null for summary record, populated for employee-level detail"),
    )
    total_referral_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Total referral cost"),
    )
    num_referrals = models.PositiveIntegerField(default=0, verbose_name=_("Number of referrals"))

    class Meta:
        verbose_name = _("Referral Cost Report")
        verbose_name_plural = _("Referral Cost Reports")
        db_table = "hrm_referral_cost_report"
        ordering = ["-report_date"]

    def __str__(self):
        if self.employee:
            return f"Referral Cost - {self.employee.fullname} - {self.report_date}"
        return f"Referral Cost Summary - {self.department.name} - {self.report_date}"
