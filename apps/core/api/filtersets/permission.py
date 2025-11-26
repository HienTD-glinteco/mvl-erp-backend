import django_filters

from apps.core.models import Permission


class PermissionFilterSet(django_filters.FilterSet):
    """FilterSet for Permission model"""

    code = django_filters.CharFilter(lookup_expr="icontains")
    name = django_filters.CharFilter(lookup_expr="icontains")
    description = django_filters.CharFilter(lookup_expr="icontains")
    module = django_filters.CharFilter(lookup_expr="iexact")
    submodule = django_filters.CharFilter(lookup_expr="iexact")
    get_all = django_filters.BooleanFilter(
        method="noop",
        help_text=(
            "If true, return all matched permissions inside the standard paginated envelope: "
            '{"count": <total>, "next": null, "previous": null, "results": [...]}.'
        ),
    )

    class Meta:
        model = Permission
        fields = ["code", "name", "description", "module", "submodule", "get_all"]

    def noop(self, queryset, name, value):
        return queryset
