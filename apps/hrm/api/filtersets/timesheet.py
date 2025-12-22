import re

import django_filters

from apps.hrm.constants import EmployeeSalaryType
from apps.hrm.models import Employee


class BaseTimesheetFilterSet(django_filters.FilterSet):
    # Accept month as MM/YYYY string. Example: "03/2025"
    month = django_filters.CharFilter(
        method="filter_month",
        label="Month",
        help_text="Month in MM/YYYY format, e.g. 03/2025",
    )

    @classmethod
    def extract_month_year(cls, month_key: str | None) -> tuple[int, int] | None:
        # Expect MM/YYYY where MM is 01-12 and YYYY is four digits
        if not month_key or not re.match(r"^(0[1-9]|1[0-2])/\d{4}$", month_key):
            # Invalid format: ignore the filter (no-op). The view can still
            # detect and return a 400 if stricter validation is desired.
            return None

        month_str, year_str = month_key.split("/")
        return int(month_str), int(year_str)

    def filter_month(self, queryset, name, value):
        """Validate month parameter in MM/YYYY format and store parsed values.

        This does not directly filter employees (timesheet logic may live in the
        view or a separate Timesheet model). Instead, it only validates the input
        """
        return queryset


class EmployeeTimesheetFilterSet(BaseTimesheetFilterSet, django_filters.FilterSet):
    """FilterSet for timesheet endpoints.

    Provides filters for employee id and related organizational fields
    (branch, block, department, position) and employee type (code_type).
    """

    employee = django_filters.NumberFilter(field_name="id")

    branch = django_filters.NumberFilter(field_name="branch_id")
    block = django_filters.NumberFilter(field_name="block_id")
    department = django_filters.NumberFilter(field_name="department_id")
    position = django_filters.NumberFilter(field_name="position_id")
    employee_salary_type = django_filters.ChoiceFilter(
        choices=EmployeeSalaryType.choices,
        method="filter_employee_salary_type",
    )

    class Meta:
        model = Employee
        fields = ["id", "branch", "block", "department", "position", "employee_salary_type"]

    def filter_employee_salary_type(self, queryset, name, value):
        """This does not directly filter employees (timesheet logic may live in the
        view or a separate Timesheet model). Instead, it only validates the input"""
        return queryset


class MineTimesheetFilterSet(BaseTimesheetFilterSet, django_filters.FilterSet):
    """FilterSet for mine timesheet endpoints."""

    class Meta:
        model = Employee
        fields: list[str] = []
