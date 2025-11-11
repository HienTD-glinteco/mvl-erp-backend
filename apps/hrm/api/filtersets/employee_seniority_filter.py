import django_filters

from apps.hrm.models import Employee


class EmployeeSeniorityFilterSet(django_filters.FilterSet):
    """FilterSet for Employee Seniority Report.

    Supports filtering by:
    - branch_id: Branch ID
    - block_id: Block ID
    - department_id: Department ID
    - function_block: Function block type (Support/Business)
    """

    branch_id = django_filters.NumberFilter(field_name="branch__id")
    block_id = django_filters.NumberFilter(field_name="block__id")
    department_id = django_filters.NumberFilter(field_name="department__id")
    function_block = django_filters.ChoiceFilter(
        field_name="block__block_type",
        choices=[
            ("support", "Support"),
            ("business", "Business"),
        ],
    )

    class Meta:
        model = Employee
        fields = ["branch_id", "block_id", "department_id", "function_block"]
