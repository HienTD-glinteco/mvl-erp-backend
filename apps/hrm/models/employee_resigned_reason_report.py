from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel

from .organization import Block, Branch, Department


class EmployeeResignedReasonReport(BaseModel):
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

    report_date = models.DateField(verbose_name=_("Report date"), db_index=True)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Branch"),
    )
    block = models.ForeignKey(
        Block,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Block"),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Department"),
    )

    # Total resigned count (sum of all reasons)
    count_resigned = models.IntegerField(default=0, verbose_name=_("Resigned count"))

    # Flat columns for each resignation reason
    agreement_termination = models.IntegerField(default=0, verbose_name=_("Agreement Termination"))
    probation_fail = models.IntegerField(default=0, verbose_name=_("Probation Fail"))
    job_abandonment = models.IntegerField(default=0, verbose_name=_("Job Abandonment"))
    disciplinary_termination = models.IntegerField(default=0, verbose_name=_("Disciplinary Termination"))
    workforce_reduction = models.IntegerField(default=0, verbose_name=_("Workforce Reduction"))
    underperforming = models.IntegerField(default=0, verbose_name=_("Underperforming"))
    contract_expired = models.IntegerField(default=0, verbose_name=_("Contract Expired"))
    voluntary_health = models.IntegerField(default=0, verbose_name=_("Voluntary - Health Reasons"))
    voluntary_personal = models.IntegerField(default=0, verbose_name=_("Voluntary - Personal Reasons"))
    voluntary_career_change = models.IntegerField(default=0, verbose_name=_("Voluntary - Career Change"))
    voluntary_other = models.IntegerField(default=0, verbose_name=_("Voluntary - Other"))
    other = models.IntegerField(default=0, verbose_name=_("Other"))

    class Meta:
        verbose_name = _("Employee Resigned Reason Report")
        verbose_name_plural = _("Employee Resigned Reason Reports")
        db_table = "hrm_employee_resigned_reason_report"
        unique_together = [["report_date", "branch", "block", "department"]]
        indexes = [
            models.Index(fields=["report_date"]),
            models.Index(fields=["branch", "block", "department"]),
        ]

    def __str__(self):
        return f"Employee Resigned Reason Report - {self.report_date} - {self.branch} / {self.block} / {self.department}"
