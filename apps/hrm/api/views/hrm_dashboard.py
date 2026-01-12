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
from apps.hrm.utils.role_data_scope import filter_queryset_by_role_data_scope
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
        summary="Common HRM stats for handling proposals, attendance, and penalties",
        description=(
            "Get HRM stats with navigation info for frontend. "
            "Each item includes path and query_params for direct navigation to filtered list views. "
            "Results are cached for 5 minutes and invalidated when relevant data changes."
        ),
        tags=["11. HRM Dashboard"],
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
        user = request.user

        # Check if user has ROOT scope (can use global cache)
        from apps.hrm.utils.role_data_scope import collect_role_allowed_units

        allowed_units = collect_role_allowed_units(user)

        if allowed_units.has_all:
            # ROOT scope users can use global cache
            cached_data = get_hrm_dashboard_cache()
            if cached_data is not None:
                serializer = HRMDashboardRealtimeSerializer(cached_data)
                return Response(serializer.data)

            # Build fresh data
            data = self._build_dashboard_data(user, allowed_units)

            # Cache the data for ROOT users only
            set_hrm_dashboard_cache(data)
        else:
            # Non-ROOT users get filtered data without caching
            data = self._build_dashboard_data(user, allowed_units)

        serializer = HRMDashboardRealtimeSerializer(data)
        return Response(serializer.data)

    def _build_dashboard_data(self, user, allowed_units) -> dict:
        """Build dashboard data from database with data scope filtering."""
        # Data scope configs for different models
        # Proposal model uses `created_by` FK to Employee, not `employee`
        proposal_scope_config = {
            "branch_field": "created_by__branch",
            "block_field": "created_by__block",
            "department_field": "created_by__department",
        }
        attendance_scope_config = {
            "branch_field": "employee__branch",
            "block_field": "employee__block",
            "department_field": "employee__department",
        }
        penalty_scope_config = {
            "branch_field": "employee__branch",
            "block_field": "employee__block",
            "department_field": "employee__department",
        }

        # Get pending proposals by type with data scope filter
        base_proposal_qs = Proposal.objects.filter(proposal_status=ProposalStatus.PENDING)
        filtered_proposal_qs = filter_queryset_by_role_data_scope(base_proposal_qs, user, proposal_scope_config)
        pending_proposals = filtered_proposal_qs.values("proposal_type").annotate(count=Count("id"))

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
                    "path": f"/decisions-proposals/proposals/{choice_value.replace('_', '-')}",
                    "query_params": {
                        "status": ProposalStatus.PENDING,
                    },
                }
            )

        # Get other statistics with data scope filter
        base_attendance_qs = AttendanceRecord.objects.filter(
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
        )
        filtered_attendance_qs = filter_queryset_by_role_data_scope(base_attendance_qs, user, attendance_scope_config)
        attendance_other_pending_count = filtered_attendance_qs.count()

        timesheet_complaints_count = proposal_counts.get(ProposalType.TIMESHEET_ENTRY_COMPLAINT, 0)

        base_penalty_qs = PenaltyTicket.objects.filter(status=PenaltyTicket.Status.UNPAID)
        filtered_penalty_qs = filter_queryset_by_role_data_scope(base_penalty_qs, user, penalty_scope_config)
        penalty_tickets_unpaid_count = filtered_penalty_qs.count()

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
                    "approve_status": AttendanceRecord.ApproveStatus.PENDING,
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
