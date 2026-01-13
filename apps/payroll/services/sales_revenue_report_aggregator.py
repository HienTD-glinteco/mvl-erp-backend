"""Service for aggregating sales revenue data into flat report model."""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.hrm.models import Department, EmployeeStatusBreakdownReport
from apps.payroll.models import SalesRevenue, SalesRevenueReportFlatModel


class SalesRevenueReportAggregator:
    """Aggregates sales revenue data into pre-calculated flat model.

    This service processes SalesRevenue records and creates/updates
    SalesRevenueReportFlatModel entries with calculated metrics.
    """

    @classmethod
    def aggregate_for_months(cls, month_dates: list[date]) -> int:
        """Aggregate sales revenue data for specified months.

        Args:
            month_dates: List of dates (first day of each month) to aggregate

        Returns:
            Number of report records created/updated
        """
        if not month_dates:
            return 0

        count = 0
        for month_date in month_dates:
            count += cls._aggregate_for_single_month(month_date)

        return count

    @classmethod
    def _aggregate_for_single_month(cls, month_date: date) -> int:
        """Aggregate data for a single month.

        Args:
            month_date: First day of the month to aggregate

        Returns:
            Number of report records created/updated for this month
        """
        # Get last day of month for employee count lookup
        if month_date.month == 12:
            last_day = date(month_date.year, 12, 31)
        else:
            next_month = date(month_date.year, month_date.month + 1, 1)
            last_day = next_month - timedelta(days=1)

        # Format month key
        month_key = month_date.strftime("%m/%Y")

        # Aggregate sales revenue by department directly from SalesRevenue
        # Only include BUSINESS function departments that are active
        sales_aggregated = (
            SalesRevenue.objects.filter(
                month=month_date,
                employee__department__function=Department.DepartmentFunction.BUSINESS,
                employee__department__is_active=True,
            )
            .values("employee__branch_id", "employee__block_id", "employee__department_id")
            .annotate(
                total_transactions=Sum("transaction_count"),
                total_revenue=Sum("revenue"),
                employees_with_revenue=Count("employee", filter=Q(revenue__gt=0), distinct=True),
                total_employees_in_sales=Count("employee", distinct=True),
                total_kpi_target=Sum("kpi_target"),
            )
        )

        if not sales_aggregated.exists():
            return 0

        # Get unique department IDs from sales data
        dept_ids = {sa["employee__department_id"] for sa in sales_aggregated}

        # Get departments with related branch/block for report creation
        departments_map = {
            d.id: d for d in Department.objects.filter(id__in=dept_ids).select_related("branch", "block")
        }

        # Build breakdown map from EmployeeStatusBreakdownReport for employee counts only
        employee_breakdowns = EmployeeStatusBreakdownReport.objects.filter(
            report_date=last_day,
            department_id__in=dept_ids,
        )
        breakdown_map = {}
        for eb in employee_breakdowns:
            key = (eb.branch_id, eb.block_id, eb.department_id)
            breakdown_map[key] = eb.count_active

        # Process aggregated data
        count = 0
        for sales_data in sales_aggregated:
            branch_id = sales_data["employee__branch_id"]
            block_id = sales_data["employee__block_id"]
            dept_id = sales_data["employee__department_id"]

            # Get department from pre-fetched map
            dept = departments_map.get(dept_id)
            if not dept:
                continue

            # Get employee count from breakdown or fallback to annotated count
            total_sales_employees = breakdown_map.get(
                (branch_id, block_id, dept_id), sales_data["total_employees_in_sales"] or 0
            )

            # Extract aggregated values
            total_transactions = sales_data["total_transactions"] or 0
            total_revenue = sales_data["total_revenue"] or 0
            employees_with_revenue = sales_data["employees_with_revenue"] or 0

            # Calculate derived fields
            total_kpi_target = sales_data["total_kpi_target"] or 0
            target_per_employee = (
                sales_data["total_kpi_target"] / total_sales_employees if total_sales_employees > 0 else 0
            )

            if total_kpi_target > 0:
                revenue_vs_target_percent = round((Decimal(total_revenue) / total_kpi_target) * 100, 2)
            else:
                revenue_vs_target_percent = Decimal("0.00")

            if total_sales_employees > 0:
                employee_with_revenue_percent = round(
                    (Decimal(employees_with_revenue) / Decimal(total_sales_employees)) * 100, 2
                )
                avg_revenue_per_employee = round(Decimal(total_revenue) / Decimal(total_sales_employees), 2)
            else:
                employee_with_revenue_percent = Decimal("0.00")
                avg_revenue_per_employee = Decimal("0.00")

            # Create or update report record
            SalesRevenueReportFlatModel.objects.update_or_create(
                report_date=month_date,
                branch=dept.branch,
                block=dept.block,
                department=dept,
                defaults={
                    "month_key": month_key,
                    "total_transactions": total_transactions,
                    "total_revenue": total_revenue,
                    "total_sales_employees": total_sales_employees,
                    "employees_with_revenue": employees_with_revenue,
                    "target_per_employee": target_per_employee,
                    "total_kpi_target": total_kpi_target,
                    "revenue_vs_target_percent": revenue_vs_target_percent,
                    "employee_with_revenue_percent": employee_with_revenue_percent,
                    "avg_revenue_per_employee": avg_revenue_per_employee,
                    "need_refresh": False,
                },
            )
            count += 1

        return count

    @classmethod
    def aggregate_from_import(cls) -> int:
        """Aggregate data for all months that have sales revenue records.

        This is called after importing sales revenue data to refresh reports.

        Returns:
            Number of report records created/updated
        """
        # Get all unique months from sales revenue
        months = SalesRevenue.objects.values_list("month", flat=True).distinct().order_by("month")

        return cls.aggregate_for_months(list(months))
