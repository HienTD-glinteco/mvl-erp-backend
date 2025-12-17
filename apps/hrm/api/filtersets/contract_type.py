import django_filters

from apps.hrm.models import ContractType


class ContractTypeFilterSet(django_filters.FilterSet):
    """FilterSet for ContractType model.

    Supports filtering by:
    - name: case-insensitive partial match (name__icontains)
    - code: case-insensitive partial match (code__icontains)
    - category: exact match (contract or appendix)
    - duration_type: exact match
    - has_social_insurance: exact match
    - working_time_type: exact match
    - created_at: exact match, date__gte, date__lte
    """

    class Meta:
        model = ContractType
        fields = {
            "name": ["icontains"],
            "code": ["icontains"],
            "category": ["exact"],
            "duration_type": ["exact"],
            "has_social_insurance": ["exact"],
            "working_time_type": ["exact"],
            "created_at": ["exact", "date__gte", "date__lte"],
        }
