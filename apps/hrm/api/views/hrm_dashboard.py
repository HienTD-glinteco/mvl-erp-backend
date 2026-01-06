"""ViewSet for HRM dashboard stats."""

from django.db.models import Count
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.api.serializers import HRMDashboardRealtimeSerializer
from apps.hrm.constants import AttendanceType, ProposalStatus, ProposalType
from apps.hrm.models import AttendanceRecord, Proposal
from apps.hrm.utils.dashboard_cache import (
    get_hrm_dashboard_cache,
    set_hrm_dashboard_cache,
)
from apps.payroll.models import PenaltyTicket
from libs.drf.base_viewset import BaseGenericViewSet


class HRMDashboardViewSet(BaseGenericViewSet):
    """HRM dashboard metrics for HR staff."""

    module = _("HRM")
    submodule = _("HRM Dashboard")
    permission_prefix = "hrm.dashboard.common"
    PERMISSION_REGISTERED_ACTIONS = {
        "realtime": {
            "name_template": _("View Common HRM realtime dashboard"),
            "description_template": _("View HRM stats for handling proposals, attendance, and penalties"),
        },
    }

    @extend_schema(
        summary="Common HRM realtime dashboard KPIs",
        description=(
            "Get HRM stats with navigation info for frontend. "
            "Each item includes path and query_params for direct navigation to filtered list views. "
            "Results are cached for 5 minutes and invalidated when relevant data changes."
        ),
        tags=[_("11.1.4. Common HRM Dashboard")],
        responses={200: HRMDashboardRealtimeSerializer},
        examples=[
            OpenApiExample(
                "Success - HRM stats with navigation",
                value={
                    "success": True,
                    "data": {
                        "proposals_pending": {
                            "key": "proposals_pending",
                            "label": "Pending Proposals",
                            "items": [
                                {
                                    "key": "proposals_paid_leave",
                                    "label": "Paid leave",
                                    "count": 3,
                                    "path": "/proposals",
                                    "query_params": {
                                        "proposal_type": "paid_leave",
                                        "proposal_status": "pending",
                                    },
                                },
                                {
                                    "key": "proposals_late_exemption",
                                    "label": "Late exemption",
                                    "count": 1,
                                    "path": "/proposals",
                                    "query_params": {
                                        "proposal_type": "late_exemption",
                                        "proposal_status": "pending",
                                    },
                                },
                            ],
                        },
                        "attendance_other_pending": {
                            "key": "attendance_other_pending",
                            "label": "Manual attendance pending",
                            "count": 2,
                            "path": "/attendance-records",
                            "query_params": {
                                "attendance_type": "other",
                                "is_pending": "true",
                            },
                        },
                        "timesheet_complaints_pending": {
                            "key": "timesheet_complaints_pending",
                            "label": "Timesheet complaints",
                            "count": 1,
                            "path": "/proposals",
                            "query_params": {
                                "proposal_type": "timesheet_entry_complaint",
                                "proposal_status": "pending",
                            },
                        },
                        "penalty_tickets_unpaid": {
                            "key": "penalty_tickets_unpaid",
                            "label": "Unpaid penalty tickets",
                            "count": 4,
                            "path": "/penalty-tickets",
                            "query_params": {"status": "UNPAID"},
                        },
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def realtime(self, request):
        """Get HRM realtime KPIs with navigation info."""
        # Try to get cached data
        cached_data = get_hrm_dashboard_cache()
        if cached_data is not None:
            serializer = HRMDashboardRealtimeSerializer(cached_data)
            return Response(serializer.data)

        # Build fresh data
        data = self._build_dashboard_data()

        # Cache the data
        set_hrm_dashboard_cache(data)

        serializer = HRMDashboardRealtimeSerializer(data)
        return Response(serializer.data)

    def _build_dashboard_data(self) -> dict:
        """Build dashboard data from database."""
        # Get pending proposals by type
        pending_proposals = (
            Proposal.objects.filter(proposal_status=ProposalStatus.PENDING)
            .values("proposal_type")
            .annotate(count=Count("id"))
        )

        # Build lookup dict
        proposal_counts = {}
        for entry in pending_proposals:
            key = entry["proposal_type"] or "unknown"
            proposal_counts[key] = entry["count"]

        # Build proposal items (exclude TIMESHEET_ENTRY_COMPLAINT as it's separate)
        proposal_items = []
        for choice_value, choice_label in ProposalType.choices:
            if choice_value == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
                continue
            count = proposal_counts.get(choice_value, 0)
            proposal_items.append(
                {
                    "key": f"proposals_{choice_value}",
                    "label": str(choice_label),
                    "count": count,
                    "path": f"/decisions-proposals/proposals/{str(choice_label).replace('_', '-')}",
                    "query_params": {
                        "status": ProposalStatus.PENDING,
                    },
                }
            )

        # Get other statistics
        attendance_other_pending_count = AttendanceRecord.objects.filter(
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
        ).count()

        timesheet_complaints_count = proposal_counts.get(ProposalType.TIMESHEET_ENTRY_COMPLAINT, 0)
        penalty_tickets_unpaid_count = PenaltyTicket.objects.filter(status=PenaltyTicket.Status.UNPAID).count()

        return {
            "proposals_pending": {
                "key": "proposals_pending",
                "label": str(_("Pending Proposals")),
                "items": proposal_items,
            },
            "attendance_other_pending": {
                "key": "attendance_other_pending",
                "label": str(_("Manual attendance pending")),
                "count": attendance_other_pending_count,
                "path": "/attendance/other-attendance",
                "query_params": {
                    "is_pending": "true",
                },
            },
            "timesheet_complaints_pending": {
                "key": "timesheet_complaints_pending",
                "label": str(_("Timesheet complaints")),
                "count": timesheet_complaints_count,
                "path": "/attendance/complaint",
                "query_params": {
                    "proposal_status__in": ProposalStatus.PENDING,
                },
            },
            "penalty_tickets_unpaid": {
                "key": "penalty_tickets_unpaid",
                "label": str(_("Unpaid penalty tickets")),
                "count": penalty_tickets_unpaid_count,
                "path": "/payroll/penalty-management",
                "query_params": {
                    "status": PenaltyTicket.Status.UNPAID,
                },
            },
        }
