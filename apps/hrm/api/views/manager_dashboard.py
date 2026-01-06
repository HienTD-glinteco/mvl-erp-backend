"""ViewSet for Manager dashboard stats."""

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.api.serializers import ManagerDashboardRealtimeSerializer
from apps.hrm.constants import ProposalVerifierStatus
from apps.hrm.models import ProposalVerifier
from apps.hrm.utils.dashboard_cache import (
    get_manager_dashboard_cache,
    set_manager_dashboard_cache,
)
from apps.payroll.models import EmployeeKPIAssessment
from libs.drf.base_viewset import BaseGenericViewSet


class ManagerDashboardViewSet(BaseGenericViewSet):
    """Manager dashboard metrics for department managers."""

    module = _("HRM")
    submodule = _("Manager Dashboard")
    permission_prefix = "hrm.dashboard.manager"
    PERMISSION_REGISTERED_ACTIONS = {
        "realtime": {
            "name_template": _("View Manager realtime dashboard"),
            "description_template": _("View manager stats for proposals to verify and KPI assessments"),
        },
    }

    @extend_schema(
        summary="Manager realtime dashboard KPIs",
        description=(
            "Get manager-specific stats with navigation info for frontend. "
            "Each item includes path and query_params for direct navigation to filtered list views. "
            "Results are cached per user for 5 minutes and invalidated when relevant data changes."
        ),
        tags=[_("11.1.3. View statistics pending processing (Manager Dashboard)")],
        responses={200: ManagerDashboardRealtimeSerializer},
        examples=[
            OpenApiExample(
                "Success - Manager stats with navigation",
                value={
                    "success": True,
                    "data": {
                        "proposals_to_verify": {
                            "key": "proposals_to_verify",
                            "label": "Proposals to verify",
                            "count": 5,
                            "path": "/decisions-proposals/proposals/manage",
                            "query_params": {
                                "status": "pending",
                            },
                        },
                        "kpi_assessments_pending": {
                            "key": "kpi_assessments_pending",
                            "label": "KPI assessments pending",
                            "count": 3,
                            "path": "/kpi/manager/period-evaluation",
                            "query_params": {
                                "finalized": "false",
                            },
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
        """Get manager realtime KPIs with navigation info."""
        user = request.user

        # Check if user has an employee record
        try:
            employee = user.employee
        except AttributeError:
            # No employee record, return zeros
            data = self._build_empty_dashboard_data()
            serializer = ManagerDashboardRealtimeSerializer(data)
            return Response(serializer.data)

        # Try to get cached data
        cached_data = get_manager_dashboard_cache(employee.id)
        if cached_data is not None:
            serializer = ManagerDashboardRealtimeSerializer(cached_data)
            return Response(serializer.data)

        # Build fresh data
        data = self._build_dashboard_data(employee)

        # Cache the data
        set_manager_dashboard_cache(employee.id, data)

        serializer = ManagerDashboardRealtimeSerializer(data)
        return Response(serializer.data)

    def _build_dashboard_data(self, employee) -> dict:
        """Build dashboard data from database for a specific manager."""
        # Count proposals pending verification for this manager
        proposals_to_verify_count = ProposalVerifier.objects.filter(
            employee=employee,
            status=ProposalVerifierStatus.PENDING,
        ).count()

        # Count KPI assessments pending manager review
        # Similar to ManagerAssessmentViewSet.current_assessments logic
        kpi_assessments_pending_count = (
            EmployeeKPIAssessment.objects.filter(
                manager=employee,
                finalized=False,
            )
            .values("employee_id")
            .distinct()
            .count()
        )

        return {
            "proposals_to_verify": {
                "key": "proposals_to_verify",
                "label": str(_("Proposals to verify")),
                "count": proposals_to_verify_count,
                "path": "/decisions-proposals/proposals/manage",
                "query_params": {
                    "status": ProposalVerifierStatus.PENDING,
                },
            },
            "kpi_assessments_pending": {
                "key": "kpi_assessments_pending",
                "label": str(_("KPI assessments pending")),
                "count": kpi_assessments_pending_count,
                "path": "/kpi/manager/period-evaluation",
                "query_params": {
                    "finalized": "false",
                },
            },
        }

    def _build_empty_dashboard_data(self) -> dict:
        """Build empty dashboard data for users without employee records."""
        return {
            "proposals_to_verify": {
                "key": "proposals_to_verify",
                "label": str(_("Proposals to verify")),
                "count": 0,
                "path": "/decisions-proposals/proposals/manage",
                "query_params": {
                    "status": ProposalVerifierStatus.PENDING,
                },
            },
            "kpi_assessments_pending": {
                "key": "kpi_assessments_pending",
                "label": str(_("KPI assessments pending")),
                "count": 0,
                "path": "/kpi/manager/period-evaluation",
                "query_params": {
                    "finalized": "false",
                },
            },
        }
