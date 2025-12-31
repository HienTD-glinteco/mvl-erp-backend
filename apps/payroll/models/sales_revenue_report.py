from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.hrm.models import Block, Branch, Department
from libs.models import BaseReportModel


class SalesRevenueReportFlatModel(BaseReportModel):
    """Pre-aggregated monthly sales revenue report by organizational unit.

    This flat model stores monthly aggregated sales data for business departments,
    including revenue totals, employee counts, and calculated KPIs. Data is
    regenerated when sales revenue is imported.

    Attributes:
        report_date: First day of the month (inherited from BaseReportModel)
        need_refresh: Flag for batch recalculation (inherited from BaseReportModel)
        month_key: Human-readable month in MM/YYYY format
        branch: Branch in organizational hierarchy
        block: Block within the branch
        department: Department within the block (BUSINESS function only)
        total_transactions: Sum of all transaction counts
        total_revenue: Sum of all revenue amounts
        total_sales_employees: Count of active sales employees (from EmployeeStatusBreakdownReport)
        employees_with_revenue: Count of employees who generated revenue
        target_per_employee: Fixed target per employee (50,000,000 VND)
        total_target: Calculated total target (total_sales_employees * target_per_employee)
        revenue_vs_target_percent: Revenue achievement percentage (total_revenue / total_target * 100)
        employee_with_revenue_percent: Percentage of employees with revenue
        avg_revenue_per_employee: Average revenue per sales employee
    """

    month_key = models.CharField(
        max_length=10,
        verbose_name=_("Month key"),
        help_text=_("Month in MM/YYYY format"),
    )
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

    # Aggregated counts
    total_transactions = models.IntegerField(
        default=0,
        verbose_name=_("Total transactions"),
    )
    total_revenue = models.BigIntegerField(
        default=0,
        verbose_name=_("Total revenue"),
    )
    total_sales_employees = models.IntegerField(
        default=0,
        verbose_name=_("Total sales employees"),
        help_text=_("Active sales employees at end of month"),
    )
    employees_with_revenue = models.IntegerField(
        default=0,
        verbose_name=_("Employees with revenue"),
        help_text=_("Count of employees who generated revenue in the month"),
    )

    # Target and calculated metrics
    target_per_employee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=50000000.00,
        verbose_name=_("Target per employee"),
        help_text=_("Fixed target per employee (50,000,000 VND)"),
    )
    total_kpi_target = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name=_("Total KPI target"),
        help_text=_("Total sales employees * Target per employee"),
    )
    revenue_vs_target_percent = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name=_("Revenue vs target (%)"),
        help_text=_("Total revenue / Total target * 100"),
    )
    employee_with_revenue_percent = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name=_("Employee with revenue (%)"),
        help_text=_("Employees with revenue / Total sales employees * 100"),
    )
    avg_revenue_per_employee = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name=_("Average revenue per employee"),
        help_text=_("Total revenue / Total sales employees"),
    )

    class Meta:
        verbose_name = _("Sales Revenue Report")
        verbose_name_plural = _("Sales Revenue Reports")
        db_table = "payroll_sales_revenue_report"
        unique_together = [["report_date", "branch", "block", "department"]]
        indexes = [
            models.Index(fields=["report_date"]),
            models.Index(fields=["branch", "block", "department"]),
            models.Index(fields=["month_key"]),
        ]

    def __str__(self):
        return f"Sales Revenue Report - {self.month_key} - {self.branch} / {self.block} / {self.department}"
