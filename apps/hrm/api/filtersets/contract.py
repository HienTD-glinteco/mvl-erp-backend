"""FilterSet for Contract model."""

from django_filters import rest_framework as filters

from apps.hrm.models import Contract


class ContractFilterSet(filters.FilterSet):
    """FilterSet for Contract model.

    Supports filtering by:
    - code: case-insensitive partial match
    - status: exact match
    - employee: exact match (Employee ID)
    - contract_type: exact match (ContractType ID)
    - sign_date: date range filtering
    - effective_date: date range filtering
    - expiration_date: date range filtering
    - branch: exact match (Branch ID via employee)
    - block: exact match (Block ID via employee)
    - department: exact match (Department ID via employee)
    """

    code = filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by contract code (case-insensitive partial match)",
    )

    status = filters.ChoiceFilter(
        choices=Contract.ContractStatus.choices,
        help_text="Filter by contract status",
    )

    employee = filters.NumberFilter(
        field_name="employee_id",
        help_text="Filter by employee ID",
    )

    contract_type = filters.NumberFilter(
        field_name="contract_type_id",
        help_text="Filter by contract type ID",
    )

    sign_date_from = filters.DateFilter(
        field_name="sign_date",
        lookup_expr="gte",
        help_text="Filter contracts signed on or after this date (format: YYYY-MM-DD)",
    )

    sign_date_to = filters.DateFilter(
        field_name="sign_date",
        lookup_expr="lte",
        help_text="Filter contracts signed on or before this date (format: YYYY-MM-DD)",
    )

    effective_date_from = filters.DateFilter(
        field_name="effective_date",
        lookup_expr="gte",
        help_text="Filter contracts effective on or after this date (format: YYYY-MM-DD)",
    )

    effective_date_to = filters.DateFilter(
        field_name="effective_date",
        lookup_expr="lte",
        help_text="Filter contracts effective on or before this date (format: YYYY-MM-DD)",
    )

    expiration_date_from = filters.DateFilter(
        field_name="expiration_date",
        lookup_expr="gte",
        help_text="Filter contracts expiring on or after this date (format: YYYY-MM-DD)",
    )

    expiration_date_to = filters.DateFilter(
        field_name="expiration_date",
        lookup_expr="lte",
        help_text="Filter contracts expiring on or before this date (format: YYYY-MM-DD)",
    )

    # Organization hierarchy filters (via employee)
    branch = filters.NumberFilter(
        field_name="employee__branch_id",
        help_text="Filter by branch ID (via employee)",
    )

    block = filters.NumberFilter(
        field_name="employee__block_id",
        help_text="Filter by block ID (via employee)",
    )

    department = filters.NumberFilter(
        field_name="employee__department_id",
        help_text="Filter by department ID (via employee)",
    )

    class Meta:
        model = Contract
        fields = [
            "code",
            "status",
            "employee",
            "contract_type",
            "sign_date_from",
            "sign_date_to",
            "effective_date_from",
            "effective_date_to",
            "expiration_date_from",
            "expiration_date_to",
            "branch",
            "block",
            "department",
        ]
