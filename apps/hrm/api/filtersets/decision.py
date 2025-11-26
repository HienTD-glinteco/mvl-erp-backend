from django_filters import rest_framework as filters

from apps.hrm.models import Decision


class DecisionFilterSet(filters.FilterSet):
    """FilterSet for Decision model.

    Supports filtering by:
    - decision_number: exact, icontains
    - name: exact, icontains
    - signing_date: exact, gte, lte (range)
    - effective_date: exact, gte, lte (range)
    - signer: exact (Employee ID)
    - signing_status: exact, in
    """

    decision_number = filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by decision number (case-insensitive partial match)",
    )

    name = filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by decision name (case-insensitive partial match)",
    )

    signing_date_from = filters.DateFilter(
        field_name="signing_date",
        lookup_expr="gte",
        help_text="Filter decisions signed on or after this date (format: YYYY-MM-DD)",
    )

    signing_date_to = filters.DateFilter(
        field_name="signing_date",
        lookup_expr="lte",
        help_text="Filter decisions signed on or before this date (format: YYYY-MM-DD)",
    )

    effective_date_from = filters.DateFilter(
        field_name="effective_date",
        lookup_expr="gte",
        help_text="Filter decisions effective on or after this date (format: YYYY-MM-DD)",
    )

    effective_date_to = filters.DateFilter(
        field_name="effective_date",
        lookup_expr="lte",
        help_text="Filter decisions effective on or before this date (format: YYYY-MM-DD)",
    )

    signer = filters.NumberFilter(
        field_name="signer_id",
        help_text="Filter by signer employee ID",
    )

    signing_status = filters.CharFilter(
        lookup_expr="exact",
        help_text="Filter by signing status (draft, issued)",
    )

    class Meta:
        model = Decision
        fields = [
            "decision_number",
            "name",
            "signing_date_from",
            "signing_date_to",
            "effective_date_from",
            "effective_date_to",
            "signer",
            "signing_status",
        ]
