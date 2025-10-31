import django_filters

from apps.hrm.models import EmployeeCertificate


class EmployeeCertificateFilterSet(django_filters.FilterSet):
    """FilterSet for EmployeeCertificate model."""

    employee = django_filters.NumberFilter(field_name="employee__id")
    certificate_types = django_filters.CharFilter(method="filter_certificate_types")
    certificate_name = django_filters.CharFilter(lookup_expr="icontains")
    issuing_organization = django_filters.CharFilter(lookup_expr="icontains")
    issue_date_from = django_filters.DateFilter(field_name="issue_date", lookup_expr="gte")
    issue_date_to = django_filters.DateFilter(field_name="issue_date", lookup_expr="lte")
    expiry_date_from = django_filters.DateFilter(field_name="expiry_date", lookup_expr="gte")
    expiry_date_to = django_filters.DateFilter(field_name="expiry_date", lookup_expr="lte")

    class Meta:
        model = EmployeeCertificate
        fields = [
            "employee",
            "certificate_type",
            "certificate_types",
            "certificate_name",
            "issuing_organization",
            "issue_date_from",
            "issue_date_to",
            "expiry_date_from",
            "expiry_date_to",
        ]

    def filter_certificate_types(self, queryset, name, value):
        """Filter by multiple certificate types (comma-separated).

        Accepts both internal keys (e.g., 'foreign_language,computer')
        and certificate codes (e.g., 'CCNN,CCTN').
        """
        if not value:
            return queryset

        # Split the value by comma
        types = [t.strip() for t in value.split(",") if t.strip()]
        if not types:
            return queryset

        # Filter by certificate_type (internal keys)
        return queryset.filter(certificate_type__in=types)
