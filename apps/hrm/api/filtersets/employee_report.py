from django_filters import rest_framework as filters

from apps.hrm.models import EmployeeWorkHistory


class EmployeeTypeConversionFilterSet(filters.FilterSet):
    from_date = filters.DateFromToRangeFilter(field_name="from_date")

    class Meta:
        model = EmployeeWorkHistory
        fields = [
            "branch",
            "block",
            "department",
            "old_employee_type",
            "new_employee_type",
            "employee",
        ]
