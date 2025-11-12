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
    position__is_leadership = django_filters.BooleanFilter()
    is_onboarding_email_sent = django_filters.BooleanFilter()
    date_of_birth__month = django_filters.NumberFilter(field_name="date_of_birth", lookup_expr="month")

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
            "contract_type",
            "status",
            "statuses",
            "gender",
            "marital_status",
            "position__is_leadership",
            "is_onboarding_email_sent",
            "date_of_birth__month",
        ]
