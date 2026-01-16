import logging
from typing import Optional

from django.db.models import Q

from apps.hrm.constants import ProposalType
from apps.hrm.models import Proposal, ProposalTimeSheetEntry, TimeSheetEntry

logger = logging.getLogger(__name__)


class ProposalSyncService:
    """Service to handle synchronization between Proposals and TimeSheetEntries."""

    @staticmethod
    def _get_proposal_date_ranges(proposal: Proposal) -> tuple[Optional[object], Optional[object]]:
        """Helper to extract date ranges for proposal types with start/end dates."""
        mapping = {
            ProposalType.LATE_EXEMPTION: ("late_exemption_start_date", "late_exemption_end_date"),
            ProposalType.POST_MATERNITY_BENEFITS: (
                "post_maternity_benefits_start_date",
                "post_maternity_benefits_end_date",
            ),
            ProposalType.MATERNITY_LEAVE: ("maternity_leave_start_date", "maternity_leave_end_date"),
            ProposalType.PAID_LEAVE: ("paid_leave_start_date", "paid_leave_end_date"),
            ProposalType.UNPAID_LEAVE: ("unpaid_leave_start_date", "unpaid_leave_end_date"),
        }

        fields = mapping.get(proposal.proposal_type)
        if fields:
            start = getattr(proposal, fields[0])
            end = getattr(proposal, fields[1])
            return start, end
        return None, None

    @classmethod
    def get_relevant_timesheet_entries_query(cls, proposal: Proposal) -> Q:
        """Construct a Q object to filter timesheet entries relevant to a proposal."""
        entries_q = Q(pk__in=[])

        # Identify relevant dates based on proposal type
        if proposal.proposal_type in [
            ProposalType.LATE_EXEMPTION,
            ProposalType.POST_MATERNITY_BENEFITS,
            ProposalType.MATERNITY_LEAVE,
            ProposalType.PAID_LEAVE,
            ProposalType.UNPAID_LEAVE,
        ]:
            start, end = cls._get_proposal_date_ranges(proposal)

            if start and end:
                entries_q = Q(date__gte=start, date__lte=end)

        elif proposal.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            if proposal.timesheet_entry_complaint_complaint_date:
                entries_q = Q(date=proposal.timesheet_entry_complaint_complaint_date)

        elif proposal.proposal_type == ProposalType.OVERTIME_WORK:
            # Overtime entries might be multiple non-contiguous dates
            # We need to access the related manager if it's already prefetched or just query it
            ot_dates = proposal.overtime_entries.values_list("date", flat=True)
            if ot_dates:
                entries_q = Q(date__in=ot_dates)

        return entries_q

    @classmethod
    def sync_entries_for_proposal(cls, proposal: Proposal) -> dict:
        """Sync timesheet entries for a proposal.

        Finds all timesheet entries for the proposal creator that fall within the
        proposal's effective range and ensures they are linked.
        """
        creator = proposal.created_by
        entries_q = cls.get_relevant_timesheet_entries_query(proposal)

        # Find relevant timesheet entries
        relevant_timesheet_ids = set(
            TimeSheetEntry.objects.filter(entries_q, employee=creator).values_list("id", flat=True)
        )

        # Get existing linked timesheet IDs
        existing_linked_ids = set(
            ProposalTimeSheetEntry.objects.filter(proposal=proposal).values_list("timesheet_entry_id", flat=True)
        )

        # Determine changes
        to_add_ids = relevant_timesheet_ids - existing_linked_ids
        to_remove_ids = existing_linked_ids - relevant_timesheet_ids

        result = {"added": len(to_add_ids), "removed": len(to_remove_ids)}

        if to_remove_ids:
            items_to_delete = ProposalTimeSheetEntry.objects.filter(
                proposal=proposal, timesheet_entry_id__in=to_remove_ids
            )
            deleted_count = items_to_delete.count()
            items_to_delete.delete()
            logger.info("Unlinked %s timesheet entries from proposal %s", deleted_count, proposal.id)

        if to_add_ids:
            added_count = 0
            for tid in to_add_ids:
                # Use get_or_create to handle potential race conditions safely
                ProposalTimeSheetEntry.objects.get_or_create(proposal=proposal, timesheet_entry_id=tid)
                added_count += 1
            logger.info("Linked %s timesheet entries to proposal %s", added_count, proposal.id)

        return result
