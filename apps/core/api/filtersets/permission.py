import django_filters

from apps.core.models import Permission


class PermissionFilterSet(django_filters.FilterSet):
    """FilterSet for Permission model"""

    code = django_filters.CharFilter(lookup_expr="icontains")
    description = django_filters.CharFilter(lookup_expr="icontains")
    module = django_filters.CharFilter(lookup_expr="iexact")
    submodule = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Permission
        fields = ["code", "description", "module", "submodule"]
