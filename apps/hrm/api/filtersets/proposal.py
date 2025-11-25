from django.db.models import Exists, OuterRef
from django_filters import rest_framework as filters

from apps.hrm.models import Proposal, ProposalTimeSheetEntry


class ProposalFilterSet(filters.FilterSet):
    """FilterSet for Proposal model."""

    timesheet_entry = filters.NumberFilter(
        method="filter_timesheet_entry",
        help_text="Filter by TimeSheetEntry ID",
    )

    def filter_timesheet_entry(self, queryset, name, value):
        """Filter proposals that have a specific timesheet entry using EXISTS subquery."""
        if not value:
            return queryset

        # Use EXISTS subquery for optimal performance
        subquery = ProposalTimeSheetEntry.objects.filter(
            proposal=OuterRef("pk"),
            timesheet_entry=value,
        )
        return queryset.filter(Exists(subquery))

    class Meta:
        model = Proposal
        fields = {
            "proposal_type": ["exact", "in"],
            "proposal_status": ["exact", "in"],
            "proposal_date": ["exact", "gte", "lte"],
        }


class TimesheetEntryComplaintProposalFilterSet(ProposalFilterSet):
    """FilterSet for TimesheetEntryComplaint proposal with additional filters."""

    created_by_department = filters.NumberFilter(
        field_name="created_by__department",
        help_text="Filter by creator's department ID",
    )

    created_by_branch = filters.NumberFilter(
        field_name="created_by__branch",
        help_text="Filter by creator's branch ID",
    )

    created_by_block = filters.NumberFilter(
        field_name="created_by__block",
        help_text="Filter by creator's block (Employee ID)",
    )

    status = filters.CharFilter(
        field_name="proposal_status",
        help_text="Filter by proposal status",
    )

    class Meta(ProposalFilterSet.Meta):
        model = Proposal
        fields = {
            **ProposalFilterSet.Meta.fields,
            "created_by": ["exact"],
            "approved_by": ["exact"],
        }
