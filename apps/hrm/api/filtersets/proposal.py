from django.db.models import Exists, OuterRef
from django_filters import rest_framework as filters

from apps.hrm.models import Proposal, ProposalTimeSheetEntry, ProposalVerifier


class ProposalFilterSet(filters.FilterSet):
    """FilterSet for Proposal model."""

    timesheet_entry = filters.NumberFilter(
        method="filter_timesheet_entry",
        help_text="Filter by TimeSheetEntry ID",
    )

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
        help_text="Filter by creator's block ID",
    )

    created_by_position = filters.NumberFilter(
        field_name="created_by__position",
        help_text="Filter by creator's position ID",
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
            "created_by": ["exact"],
            "approved_by": ["exact"],
        }


class MeProposalFilterSet(ProposalFilterSet):
    class Meta:
        model = Proposal
        fields = {
            "proposal_type": ["exact", "in"],
            "proposal_status": ["exact", "in"],
            "proposal_date": ["exact", "gte", "lte"],
            "approved_by": ["exact"],
        }


class ProposalVerifierFilterSet(filters.FilterSet):
    """FilterSet for Proposal model used by verifiers."""

    class Meta:
        model = ProposalVerifier
        fields = {
            "proposal": ["exact"],
            "proposal__proposal_type": ["exact", "in"],
            "proposal__proposal_status": ["exact", "in"],
            "status": ["exact", "in"],
            "employee": ["exact"],
        }


class MeProposalVerifierFilterSet(filters.FilterSet):
    """FilterSet for Proposal model used by verifiers."""

    class Meta:
        model = ProposalVerifier
        fields = {
            "proposal": ["exact"],
            "proposal__proposal_type": ["exact", "in"],
            "proposal__proposal_status": ["exact", "in"],
            "status": ["exact", "in"],
        }
