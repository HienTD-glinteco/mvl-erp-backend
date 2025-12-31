import django_filters

from apps.hrm.models import Employee


class EmployeeFilterSet(django_filters.FilterSet):
    """FilterSet for Employee model"""

    code = django_filters.CharFilter(lookup_expr="icontains")
    fullname = django_filters.CharFilter(lookup_expr="icontains")
    username = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    phone = django_filters.CharFilter(lookup_expr="icontains")
    citizen_id = django_filters.CharFilter(lookup_expr="icontains")
    statuses = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=Employee.Status.choices,
    )
    branch = django_filters.NumberFilter(field_name="branch")
    block = django_filters.NumberFilter(field_name="block")
    department = django_filters.NumberFilter(field_name="department")
    position = django_filters.NumberFilter(field_name="position")
    position__is_leadership = django_filters.BooleanFilter()
    is_onboarding_email_sent = django_filters.BooleanFilter()
    date_of_birth__month = django_filters.NumberFilter(field_name="date_of_birth", lookup_expr="month")
    has_citizen_id_file = django_filters.BooleanFilter(method="filter_has_citizen_id_file")
    is_os_code_type = django_filters.BooleanFilter(method="filter_is_os_code_type")

    class Meta:
        model = Employee
        fields = [
            "code",
            "code_type",
            "fullname",
            "username",
            "email",
            "phone",
            "citizen_id",
            "branch",
            "block",
            "department",
            "position",
            "status",
            "statuses",
            "gender",
            "marital_status",
            "position__is_leadership",
            "is_onboarding_email_sent",
            "date_of_birth__month",
            "has_citizen_id_file",
            "is_os_code_type",
        ]

    def filter_has_citizen_id_file(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.filter(citizen_id_file__isnull=not value)

    def filter_is_os_code_type(self, queryset, name, value):
        if value is None:
            return queryset
        if value:
            return queryset.filter(code_type=Employee.CodeType.OS)
        return queryset.exclude(code_type=Employee.CodeType.OS)


class EmployeeDropdownFilterSet(django_filters.FilterSet):
    """Slim filterset for Employee dropdown endpoint."""

    code = django_filters.CharFilter(lookup_expr="icontains")
    branch = django_filters.NumberFilter(field_name="branch")
    block = django_filters.NumberFilter(field_name="block")
    department = django_filters.NumberFilter(field_name="department")
    position = django_filters.NumberFilter(field_name="position")
    status = django_filters.ChoiceFilter(field_name="status", choices=Employee.Status.choices)
    statuses = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=Employee.Status.choices,
    )

    class Meta:
        model = Employee
        fields = ["code", "branch", "block", "department", "position", "status", "statuses"]
