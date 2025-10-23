import django_filters

from apps.hrm.models import Employee


class EmployeeFilterSet(django_filters.FilterSet):
    """FilterSet for Employee model"""

    code = django_filters.CharFilter(lookup_expr="icontains")
    fullname = django_filters.CharFilter(lookup_expr="icontains")
    username = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    phone = django_filters.CharFilter(lookup_expr="icontains")
    statuses = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=Employee.Status.choices,
    )

    class Meta:
        model = Employee
        fields = [
            "code",
            "code_type",
            "fullname",
            "username",
            "email",
            "phone",
            "branch",
            "block",
            "department",
            "position",
            "contract_type",
            "status",
            "statuses",
            "gender",
            "marital_status",
        ]
