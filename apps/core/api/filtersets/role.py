import django_filters

from apps.core.models import Role


class RoleFilterSet(django_filters.FilterSet):
    """FilterSet for Role model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    is_system_role = django_filters.BooleanFilter()

    class Meta:
        model = Role
        fields = ["name", "code", "is_system_role"]
