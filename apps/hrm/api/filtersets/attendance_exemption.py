import django_filters

from apps.hrm.models import AttendanceExemption


class AttendanceExemptionFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceExemption model with organizational filtering."""

    branch = django_filters.NumberFilter(field_name="employee__branch__id")
    block = django_filters.NumberFilter(field_name="employee__block__id")
    department = django_filters.NumberFilter(field_name="employee__department__id")
    position = django_filters.NumberFilter(field_name="employee__position__id")
    effective_date_from = django_filters.DateFilter(
        field_name="effective_date",
        lookup_expr="gte",
    )
    effective_date_to = django_filters.DateFilter(
        field_name="effective_date",
        lookup_expr="lte",
    )
    end_date_from = django_filters.DateFilter(
        field_name="end_date",
        lookup_expr="gte",
    )
    end_date_to = django_filters.DateFilter(
        field_name="end_date",
        lookup_expr="lte",
    )
    status = django_filters.ChoiceFilter(choices=AttendanceExemption.Status.choices)

    class Meta:
        model = AttendanceExemption
        fields = [
            "branch",
            "block",
            "department",
            "position",
            "effective_date_from",
            "effective_date_to",
            "end_date_from",
            "end_date_to",
            "status",
        ]
