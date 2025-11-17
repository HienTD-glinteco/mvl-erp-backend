import re

import django_filters

from apps.hrm.constants import EmployeeSalaryType
from apps.hrm.models import Employee


class TimesheetFilterSet(django_filters.FilterSet):
    """FilterSet for timesheet endpoints.

    Provides filters for employee id and related organizational fields
    (branch, block, department, position) and employee type (code_type).
    """

    # Accept month as MM/YYYY string. Example: "03/2025"
    month = django_filters.CharFilter(
        method="filter_month",
        label="Month",
        help_text="Month in MM/YYYY format, e.g. 03/2025",
    )
    employee = django_filters.NumberFilter(field_name="id")

    branch = django_filters.NumberFilter(field_name="branch_id")
    block = django_filters.NumberFilter(field_name="block_id")
    department = django_filters.NumberFilter(field_name="department_id")
    position = django_filters.NumberFilter(field_name="position_id")

    # TODO: implement actual filter logic
    employee_salary_type = django_filters.ChoiceFilter(choices=EmployeeSalaryType.choices)

    def filter_month(self, queryset, name, value):
        """Validate month parameter in MM/YYYY format and store parsed values.

        This does not directly filter employees (timesheet logic may live in the
        view or a separate Timesheet model). Instead, it validates the input
        and exposes parsed month/year via the filterset instance as
        `self._timesheet_month` and `self._timesheet_year` for downstream use.
        """
        if not value:
            return queryset

        # Expect MM/YYYY where MM is 01-12 and YYYY is four digits
        if not re.match(r"^(0[1-9]|1[0-2])/\d{4}$", value):
            # Invalid format: ignore the filter (no-op). The view can still
            # detect and return a 400 if stricter validation is desired.
            return queryset

        month_str, year_str = value.split("/")
        self._timesheet_month = int(month_str)
        self._timesheet_year = int(year_str)

        return queryset

    class Meta:
        model = Employee
        fields = ["employee", "branch", "block", "department", "position", "employee_salary_type"]
