import django_filters
from django.db import models

from apps.core.models import Role, User
from apps.hrm.models import Block, Branch, Department, Position


class EmployeeRoleFilterSet(django_filters.FilterSet):
    """FilterSet for filtering employees by role and organizational structure"""

    # Text search on employee name or role name
    search = django_filters.CharFilter(method="filter_search")

    # Organization filters
    branch = django_filters.ModelChoiceFilter(
        field_name="organization_positions__department__block__branch",
        queryset=Branch.objects.filter(is_active=True),
        distinct=True,
    )
    block = django_filters.ModelChoiceFilter(
        field_name="organization_positions__department__block",
        queryset=Block.objects.filter(is_active=True),
        distinct=True,
    )
    department = django_filters.ModelChoiceFilter(
        field_name="organization_positions__department",
        queryset=Department.objects.filter(is_active=True),
        distinct=True,
    )
    position = django_filters.ModelChoiceFilter(
        field_name="organization_positions__position",
        queryset=Position.objects.filter(is_active=True),
        distinct=True,
    )
    role = django_filters.ModelChoiceFilter(
        queryset=Role.objects.all(),
    )

    # Additional filters for active/primary organization positions
    is_primary = django_filters.BooleanFilter(field_name="organization_positions__is_primary")
    is_org_active = django_filters.BooleanFilter(field_name="organization_positions__is_active")

    class Meta:
        model = User
        fields = ["search", "branch", "block", "department", "position", "role", "is_primary", "is_org_active"]

    def filter_search(self, queryset, name, value):
        """
        Filter by employee name or role name.
        Searches for continuous substring match (case-insensitive).
        """
        if not value:
            return queryset

        return queryset.filter(
            models.Q(first_name__icontains=value)
            | models.Q(last_name__icontains=value)
            | models.Q(role__name__icontains=value)
        )
