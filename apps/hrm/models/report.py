from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel

from .organization import Block, Branch, Department


@audit_logging_register
class EmployeeStatusBreakdownReport(BaseModel):
    """Daily employee status breakdown report.

    Stores per-day headcount and resignation breakdowns for a specific organizational unit.
    Each record represents data for one day across branch, block, and department.

    Attributes:
        report_date: Date of the report
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
    count_active = models.IntegerField(default=0, verbose_name=_("Active count"))
    count_onboarding = models.IntegerField(default=0, verbose_name=_("Onboarding count"))
    count_maternity_leave = models.IntegerField(default=0, verbose_name=_("Maternity leave count"))
    count_unpaid_leave = models.IntegerField(default=0, verbose_name=_("Unpaid leave count"))
    count_resigned = models.IntegerField(default=0, verbose_name=_("Resigned count"))
    total_not_resigned = models.IntegerField(default=0, verbose_name=_("Total not resigned"))
    count_resigned_reasons = models.JSONField(default=dict, verbose_name=_("Resignation reasons breakdown"))

    class Meta:
        verbose_name = _("Employee Status Breakdown Report")
        verbose_name_plural = _("Employee Status Breakdown Reports")
        db_table = "hrm_employee_status_breakdown_report"
        unique_together = [["report_date", "branch", "block", "department"]]
        indexes = [
            models.Index(fields=["report_date"]),
            models.Index(fields=["branch", "block", "department"]),
        ]

    def __str__(self):
        return f"Employee Status Breakdown - {self.report_date} - {self.branch} / {self.block} / {self.department}"
