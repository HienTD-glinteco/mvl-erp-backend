import django_filters

from apps.hrm.constants import EmployeeSalaryType
from apps.hrm.models import Employee


class TimesheetFilterSet(django_filters.FilterSet):
    """FilterSet for timesheet endpoints.

    Provides filters for employee id and related organizational fields
    (branch, block, department, position) and employee type (code_type).
    """

    employee = django_filters.NumberFilter(field_name="employee__id")

    branch = django_filters.NumberFilter(field_name="employee__branch__id")
    block = django_filters.NumberFilter(field_name="employee__block__id")
    department = django_filters.NumberFilter(field_name="employee__department__id")
    position = django_filters.NumberFilter(field_name="employee__position__id")

    # TODO: implement actual filter logic
    employee_salary_type = django_filters.ChoiceFilter(choices=EmployeeSalaryType.choices)

    class Meta:
        model = Employee
        fields = ["employee", "branch", "block", "department", "position", "employee_salary_type"]
