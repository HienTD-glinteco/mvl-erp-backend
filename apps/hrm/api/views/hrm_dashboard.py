"""ViewSet for HRM dashboard stats."""

from collections import OrderedDict

from django.db.models import Count
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.api.serializers import HRMDashboardRealtimeSerializer
from apps.hrm.constants import AttendanceType, ProposalStatus, ProposalType
from apps.hrm.models import AttendanceRecord, Proposal
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
        description="Get HRM stats: pending proposals by type, pending manual attendance, pending complaint proposals, and unpaid penalty tickets.",
        tags=[_("11.1. Management Dashboard")],
        responses={200: HRMDashboardRealtimeSerializer},
        examples=[
            OpenApiExample(
                "Success - HRM stats",
                value={
                    "success": True,
                    "data": {
                        "proposals_pending": {
                            "paid_leave": 3,
                            "timesheet_entry_complaint": 1,
                        },
                        "attendance_other_pending": 2,
                        "timesheet_complaints_pending": 1,
                        "penalty_tickets_unpaid": 4,
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
        demand_counts = OrderedDict()
        for choice, __ in ProposalType.choices:
            demand_counts[choice] = 0
        demand_counts["unknown"] = 0

        pending_proposals = (
            Proposal.objects.filter(proposal_status=ProposalStatus.PENDING)
            .values("proposal_type")
            .annotate(count=Count("id"))
        )
        for entry in pending_proposals:
            key = entry["proposal_type"] or "unknown"
            demand_counts[key] = entry["count"]

        attendance_other_pending = AttendanceRecord.objects.filter(
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
        ).count()

        timesheet_complaints_pending = demand_counts.pop(ProposalType.TIMESHEET_ENTRY_COMPLAINT, 0)
        penalty_tickets_unpaid = PenaltyTicket.objects.filter(status=PenaltyTicket.Status.UNPAID).count()

        data = {
            "proposals_pending": demand_counts,
            "attendance_other_pending": attendance_other_pending,
            "timesheet_complaints_pending": timesheet_complaints_pending,
            "penalty_tickets_unpaid": penalty_tickets_unpaid,
        }

        serializer = HRMDashboardRealtimeSerializer(data)
        return Response(serializer.data)
