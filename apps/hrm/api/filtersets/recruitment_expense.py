import django_filters

from apps.hrm.models import RecruitmentExpense


class RecruitmentExpenseFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentExpense model"""

    date = django_filters.DateFilter()
    date__gte = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date__lte = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    recruitment_source = django_filters.NumberFilter(field_name="recruitment_source__id")
    recruitment_channel = django_filters.NumberFilter(field_name="recruitment_channel__id")
    recruitment_request = django_filters.NumberFilter(field_name="recruitment_request__id")
    referee = django_filters.NumberFilter(field_name="referee__id")
    referrer = django_filters.NumberFilter(field_name="referrer__id")

    class Meta:
        model = RecruitmentExpense
        fields = [
            "date",
            "date__gte",
            "date__lte",
            "recruitment_source",
            "recruitment_channel",
            "recruitment_request",
            "referee",
            "referrer",
        ]
