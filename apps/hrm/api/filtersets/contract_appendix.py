"""FilterSet for ContractAppendix model."""

from django_filters import rest_framework as filters

from apps.hrm.models import ContractAppendix


class ContractAppendixFilterSet(filters.FilterSet):
    """FilterSet for ContractAppendix model.

    Supports filtering by:
    - code: case-insensitive partial match
    - appendix_code: case-insensitive partial match
    - contract: exact match (Contract ID)
    - sign_date: date range filtering
    - effective_date: date range filtering
    - employee: exact match (Employee ID via contract)
    - branch: exact match (Branch ID via contract.employee)
    - block: exact match (Block ID via contract.employee)
    - department: exact match (Department ID via contract.employee)
    """

    code = filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by appendix number (case-insensitive partial match)",
    )

    appendix_code = filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by appendix code (case-insensitive partial match)",
    )

    contract = filters.NumberFilter(
        field_name="contract_id",
        help_text="Filter by contract ID",
    )

    sign_date_from = filters.DateFilter(
        field_name="sign_date",
        lookup_expr="gte",
        help_text="Filter appendices signed on or after this date (format: YYYY-MM-DD)",
    )

    sign_date_to = filters.DateFilter(
        field_name="sign_date",
        lookup_expr="lte",
        help_text="Filter appendices signed on or before this date (format: YYYY-MM-DD)",
    )

    effective_date_from = filters.DateFilter(
        field_name="effective_date",
        lookup_expr="gte",
        help_text="Filter appendices effective on or after this date (format: YYYY-MM-DD)",
    )

    effective_date_to = filters.DateFilter(
        field_name="effective_date",
        lookup_expr="lte",
        help_text="Filter appendices effective on or before this date (format: YYYY-MM-DD)",
    )

    # Organization hierarchy filters (via contract.employee)
    employee = filters.NumberFilter(
        field_name="contract__employee_id",
        help_text="Filter by employee ID (via contract)",
    )

    branch = filters.NumberFilter(
        field_name="contract__employee__branch_id",
        help_text="Filter by branch ID (via contract.employee)",
    )

    block = filters.NumberFilter(
        field_name="contract__employee__block_id",
        help_text="Filter by block ID (via contract.employee)",
    )

    department = filters.NumberFilter(
        field_name="contract__employee__department_id",
        help_text="Filter by department ID (via contract.employee)",
    )

    class Meta:
        model = ContractAppendix
        fields = [
            "code",
            "appendix_code",
            "contract",
            "sign_date_from",
            "sign_date_to",
            "effective_date_from",
            "effective_date_to",
            "employee",
            "branch",
            "block",
            "department",
        ]
