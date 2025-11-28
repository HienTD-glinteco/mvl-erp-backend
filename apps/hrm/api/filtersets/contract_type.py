import django_filters

from apps.hrm.models import ContractType


class ContractTypeFilterSet(django_filters.FilterSet):
    """FilterSet for ContractType model.

    Supports filtering by:
    - name: case-insensitive partial match
    - code: case-insensitive partial match
    - duration_type: exact match
    - has_social_insurance: exact match
    - working_time_type: exact match
    - created_at: date range filtering
    """

    name = django_filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by contract type name (case-insensitive partial match)",
    )

    code = django_filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by contract type code (case-insensitive partial match)",
    )

    duration_type = django_filters.ChoiceFilter(
        choices=ContractType.DurationType.choices,
        help_text="Filter by duration type (indefinite or fixed)",
    )

    has_social_insurance = django_filters.BooleanFilter(
        help_text="Filter by social insurance status",
    )

    working_time_type = django_filters.ChoiceFilter(
        choices=ContractType.WorkingTimeType.choices,
        help_text="Filter by working time type",
    )

    created_at_from = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
        help_text="Filter contract types created on or after this date (format: YYYY-MM-DD)",
    )

    created_at_to = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
        help_text="Filter contract types created on or before this date (format: YYYY-MM-DD)",
    )

    class Meta:
        model = ContractType
        fields = [
            "name",
            "code",
            "duration_type",
            "has_social_insurance",
            "working_time_type",
            "created_at_from",
            "created_at_to",
        ]
