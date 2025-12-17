import django_filters

from apps.hrm.models import EmployeeCertificate


class EmployeeCertificateFilterSet(django_filters.FilterSet):
    """FilterSet for EmployeeCertificate model.

    Supports filtering by:
    - employee: exact match (Employee ID)
    - certificate_type: exact match
    - certificate_types: comma-separated multiple certificate types
    - certificate_name: case-insensitive partial match
    - issuing_organization: case-insensitive partial match
    - issue_date_from/to: date range filtering
    - effective_date_from/to: date range filtering
    - expiry_date_from/to: date range filtering
    - status: multiple choice filter (Valid, Near Expiry, Expired)
    - branch: exact match (Branch ID via employee)
    - block: exact match (Block ID via employee)
    - department: exact match (Department ID via employee)
    - position: exact match (Position ID via employee)
    """

    employee = django_filters.NumberFilter(
        field_name="employee__id",
        help_text="Filter by employee ID",
    )
    certificate_types = django_filters.CharFilter(
        method="filter_certificate_types",
        help_text="Filter by multiple certificate types (comma-separated, e.g., 'foreign_language,computer')",
    )
    certificate_name = django_filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by certificate name (case-insensitive partial match)",
    )
    issuing_organization = django_filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by issuing organization (case-insensitive partial match)",
    )
    issue_date_from = django_filters.DateFilter(
        field_name="issue_date",
        lookup_expr="gte",
        help_text="Filter certificates issued on or after this date (format: YYYY-MM-DD)",
    )
    issue_date_to = django_filters.DateFilter(
        field_name="issue_date",
        lookup_expr="lte",
        help_text="Filter certificates issued on or before this date (format: YYYY-MM-DD)",
    )
    effective_date_from = django_filters.DateFilter(
        field_name="effective_date",
        lookup_expr="gte",
        help_text="Filter certificates effective on or after this date (format: YYYY-MM-DD)",
    )
    effective_date_to = django_filters.DateFilter(
        field_name="effective_date",
        lookup_expr="lte",
        help_text="Filter certificates effective on or before this date (format: YYYY-MM-DD)",
    )
    expiry_date_from = django_filters.DateFilter(
        field_name="expiry_date",
        lookup_expr="gte",
        help_text="Filter certificates expiring on or after this date (format: YYYY-MM-DD)",
    )
    expiry_date_to = django_filters.DateFilter(
        field_name="expiry_date",
        lookup_expr="lte",
        help_text="Filter certificates expiring on or before this date (format: YYYY-MM-DD)",
    )
    status = django_filters.MultipleChoiceFilter(
        choices=EmployeeCertificate.Status.choices,
        help_text="Filter by certificate status (supports multiple values)",
    )

    # Organization hierarchy filters (via employee)
    branch = django_filters.NumberFilter(
        field_name="employee__branch__id",
        help_text="Filter by branch ID (via employee)",
    )
    block = django_filters.NumberFilter(
        field_name="employee__block__id",
        help_text="Filter by block ID (via employee)",
    )
    department = django_filters.NumberFilter(
        field_name="employee__department__id",
        help_text="Filter by department ID (via employee)",
    )
    position = django_filters.NumberFilter(
        field_name="employee__position__id",
        help_text="Filter by position ID (via employee)",
    )

    class Meta:
        model = EmployeeCertificate
        fields = {
            "employee": ["exact"],
            "certificate_type": ["exact"],
            "certificate_name": ["icontains"],
            "issuing_organization": ["icontains"],
            "issue_date": ["gte", "lte"],
            "effective_date": ["gte", "lte"],
            "expiry_date": ["gte", "lte"],
            "status": ["exact"],
        }

    def filter_certificate_types(self, queryset, name, value):
        """Filter by multiple certificate types (comma-separated).

        Accepts internal keys (e.g., 'foreign_language,computer').
        """
        if not value:
            return queryset

        # Split the value by comma
        types = [t.strip() for t in value.split(",") if t.strip()]
        if not types:
            return queryset

        # Filter by certificate_type (internal keys)
        return queryset.filter(certificate_type__in=types)
