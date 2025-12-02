from django.db import models

from libs.models import BaseReportModel

from .organization import Block, Branch, Department


class EmployeeStatusBreakdownReport(BaseReportModel):
    """Daily employee status breakdown report.

    Stores per-day headcount and resignation breakdowns for a specific organizational unit.
    Each record represents data for one day across branch, block, and department.

    Attributes:
        report_date: Date of the report (inherited from BaseReportModel)
        need_refresh: Flag indicating if report needs recalculation by batch task (inherited from BaseReportModel)
        branch: Branch in the organizational hierarchy
        block: Block within the branch
        department: Department within the block
        count_active: Number of active employees
        count_onboarding: Number of employees in onboarding status
        count_maternity_leave: Number of employees on maternity leave
        count_unpaid_leave: Number of employees on unpaid leave
        count_resigned: Number of resigned employees
        total_not_resigned: Total count excluding resigned employees
        count_resigned_reasons: JSON field storing resignation reason counts
    """

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Branch",
    )
    block = models.ForeignKey(
        Block,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Block",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Department",
    )
    count_active = models.IntegerField(default=0, verbose_name="Active count")
    count_onboarding = models.IntegerField(default=0, verbose_name="Onboarding count")
    count_maternity_leave = models.IntegerField(default=0, verbose_name="Maternity leave count")
    count_unpaid_leave = models.IntegerField(default=0, verbose_name="Unpaid leave count")
    count_resigned = models.IntegerField(default=0, verbose_name="Resigned count")
    total_not_resigned = models.IntegerField(default=0, verbose_name="Total not resigned")
    count_resigned_reasons = models.JSONField(default=dict, verbose_name="Resignation reasons breakdown")

    class Meta:
        verbose_name = "Employee Status Breakdown Report"
        verbose_name_plural = "Employee Status Breakdown Reports"
        db_table = "hrm_employee_status_breakdown_report"
        unique_together = [["report_date", "branch", "block", "department"]]
        indexes = [
            models.Index(fields=["report_date"]),
            models.Index(fields=["branch", "block", "department"]),
        ]

    def __str__(self):
        return f"Employee Status Breakdown - {self.report_date} - {self.branch} / {self.block} / {self.department}"


class EmployeeResignedReasonReport(BaseReportModel):
    """Daily employee resignation reason report.

    Stores pre-aggregated daily resignation reason counts per organizational unit.
    Each row represents one day's data for one (Branch, Block, Department) tuple.
    Flat integer columns for each fixed resignation reason for efficient aggregation.

    Attributes:
        report_date: Date of the report
        branch: Branch in the organizational hierarchy
        block: Block within the branch
        department: Department within the block
        count_resigned: Total resigned count (sum of all reasons)
        agreement_termination: Count for Agreement Termination reason
        probation_fail: Count for Probation Fail reason
        job_abandonment: Count for Job Abandonment reason
        disciplinary_termination: Count for Disciplinary Termination reason
        workforce_reduction: Count for Workforce Reduction reason
        underperforming: Count for Underperforming reason
        contract_expired: Count for Contract Expired reason
        voluntary_health: Count for Voluntary - Health Reasons
        voluntary_personal: Count for Voluntary - Personal Reasons
        voluntary_career_change: Count for Voluntary - Career Change
        voluntary_other: Count for Voluntary - Other
        other: Count for Other reason
    """

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Branch",
    )
    block = models.ForeignKey(
        Block,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Block",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Department",
    )

    # Total resigned count (sum of all reasons)
    count_resigned = models.IntegerField(default=0, verbose_name="Resigned count")

    # Flat columns for each resignation reason
    agreement_termination = models.IntegerField(default=0, verbose_name="Agreement Termination")
    probation_fail = models.IntegerField(default=0, verbose_name="Probation Fail")
    job_abandonment = models.IntegerField(default=0, verbose_name="Job Abandonment")
    disciplinary_termination = models.IntegerField(default=0, verbose_name="Disciplinary Termination")
    workforce_reduction = models.IntegerField(default=0, verbose_name="Workforce Reduction")
    underperforming = models.IntegerField(default=0, verbose_name="Underperforming")
    contract_expired = models.IntegerField(default=0, verbose_name="Contract Expired")
    voluntary_health = models.IntegerField(default=0, verbose_name="Voluntary - Health Reasons")
    voluntary_personal = models.IntegerField(default=0, verbose_name="Voluntary - Personal Reasons")
    voluntary_career_change = models.IntegerField(default=0, verbose_name="Voluntary - Career Change")
    voluntary_other = models.IntegerField(default=0, verbose_name="Voluntary - Other")
    other = models.IntegerField(default=0, verbose_name="Other")

    class Meta:
        verbose_name = "Employee Resigned Reason Report"
        verbose_name_plural = "Employee Resigned Reason Reports"
        db_table = "hrm_employee_resigned_reason_report"
        unique_together = [["report_date", "branch", "block", "department"]]
        indexes = [
            models.Index(fields=["report_date"]),
            models.Index(fields=["branch", "block", "department"]),
        ]

    def __str__(self):
        return (
            f"Employee Resigned Reason Report - {self.report_date} - {self.branch} / {self.block} / {self.department}"
        )
