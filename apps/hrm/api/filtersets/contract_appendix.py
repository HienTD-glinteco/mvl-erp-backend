"""FilterSet for Contract Appendix (using Contract model with category='appendix')."""

from django_filters import rest_framework as filters

from apps.hrm.models import Contract


class ContractAppendixFilterSet(filters.FilterSet):
    """FilterSet for Contract Appendix (using Contract model).

    Supports filtering by:
    - code: case-insensitive partial match
    - contract_number: case-insensitive partial match
    - parent_contract: exact match (Parent Contract ID)
    - sign_date: date range filtering
    - effective_date: date range filtering
    - status: exact match
    - employee: exact match (Employee ID)
    - branch: exact match (Branch ID via employee)
    - block: exact match (Block ID via employee)
    - department: exact match (Department ID via employee)
    """

    code = filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by appendix code (case-insensitive partial match)",
    )

    contract_number = filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter by contract number (case-insensitive partial match)",
    )

    parent_contract = filters.NumberFilter(
        field_name="parent_contract_id",
        help_text="Filter by parent contract ID",
    )

    status = filters.ChoiceFilter(
        choices=Contract.ContractStatus.choices,
        help_text="Filter by appendix status",
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

    # Organization hierarchy filters (via employee)
    employee = filters.NumberFilter(
        field_name="employee_id",
        help_text="Filter by employee ID",
    )

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
            "contract_number",
            "parent_contract",
            "status",
            "sign_date_from",
            "sign_date_to",
            "effective_date_from",
            "effective_date_to",
            "employee",
            "branch",
            "block",
            "department",
        ]
