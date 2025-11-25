import django_filters

from apps.core.models import Role, User
from apps.hrm.models import Block, Branch, Department, Position


class EmployeeRoleFilterSet(django_filters.FilterSet):
    """FilterSet for filtering employees by role and organizational structure"""

    # Organization filters
    branch = django_filters.ModelChoiceFilter(
        field_name="employee__branch",
        queryset=Branch.objects.filter(is_active=True),
        distinct=True,
    )
    block = django_filters.ModelChoiceFilter(
        field_name="employee__block",
        queryset=Block.objects.filter(is_active=True),
        distinct=True,
    )
    department = django_filters.ModelChoiceFilter(
        field_name="employee__department",
        queryset=Department.objects.filter(is_active=True),
        distinct=True,
    )
    position = django_filters.ModelChoiceFilter(
        field_name="employee__position",
        queryset=Position.objects.filter(is_active=True),
        distinct=True,
    )
    role = django_filters.ModelChoiceFilter(
        queryset=Role.objects.all(),
    )

    class Meta:
        model = User
        fields = ["branch", "block", "department", "position", "role"]
