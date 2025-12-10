import django_filters

from apps.core.models import Role, User
from apps.hrm.models import Block, Branch, Department, Position


class EmployeeRoleFilterSet(django_filters.FilterSet):
    """FilterSet for filtering employees by role and organizational structure"""

    # Organization filters
    branch = django_filters.NumberFilter(field_name="employee__branch", distinct=True)
    block = django_filters.NumberFilter(field_name="employee__block", distinct=True)
    department = django_filters.NumberFilter(field_name="employee__department", distinct=True)
    position = django_filters.NumberFilter(field_name="employee__position", distinct=True)
    role = django_filters.NumberFilter(field_name="role", distinct=True)

    class Meta:
        model = User
        fields = ["branch", "block", "department", "position", "role"]
