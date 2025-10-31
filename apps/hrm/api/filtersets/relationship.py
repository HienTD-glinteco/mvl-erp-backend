import django_filters

from apps.hrm.models import Relationship


class RelationshipFilterSet(django_filters.FilterSet):
    """FilterSet for Relationship model"""

    search = django_filters.CharFilter(method="filter_search")
    employee = django_filters.NumberFilter(field_name="employee__id")
    relation_type = django_filters.CharFilter(field_name="relation_type", lookup_expr="iexact")
    is_active = django_filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = Relationship
        fields = ["employee", "relation_type", "is_active", "search"]

    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if not value:
            return queryset

        return queryset.filter(
            django_filters.Q(employee_code__icontains=value)
            | django_filters.Q(employee_name__icontains=value)
            | django_filters.Q(relative_name__icontains=value)
            | django_filters.Q(relation_type__icontains=value)
        )
