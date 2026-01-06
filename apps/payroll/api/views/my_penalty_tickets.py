"""ViewSet for user's own penalty tickets (mobile)."""

from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter

from apps.core.api.permissions import RoleBasedPermission
from apps.payroll.api.filtersets import PenaltyTicketFilterSet
from apps.payroll.api.serializers import PenaltyTicketSerializer
from apps.payroll.models import PenaltyTicket
from libs.drf.base_viewset import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List my penalty tickets",
        description="Retrieve a paginated list of the current user's penalty tickets.",
        tags=["10.3: My Penalty Tickets"],
        examples=[
            OpenApiExample(
                "Success - My penalty ticket list",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "code": "RVF-202511-0001",
                                "month": "11/2025",
                                "employee_id": 123,
                                "employee_code": "E0001",
                                "employee_name": "John Doe",
                                "violation_count": 1,
                                "violation_type": "UNDER_10_MINUTES",
                                "amount": 100000,
                                "status": "UNPAID",
                                "note": "Uniform violation - missing name tag",
                                "payment_date": None,
                                "attachments": [],
                                "created_at": "2025-11-15T10:00:00Z",
                                "updated_at": "2025-11-15T10:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get my penalty ticket details",
        description="Retrieve detailed information about a specific penalty ticket belonging to the current user.",
        tags=["10.3: My Penalty Tickets"],
        examples=[
            OpenApiExample(
                "Success - My penalty ticket detail",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "code": "RVF-202511-0001",
                        "month": "11/2025",
                        "employee_id": 123,
                        "employee_code": "E0001",
                        "employee_name": "John Doe",
                        "violation_count": 1,
                        "violation_type": "UNDER_10_MINUTES",
                        "amount": 100000,
                        "status": "UNPAID",
                        "note": "Uniform violation",
                        "attachments": [],
                        "payment_date": None,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Not found",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Not found."},
                },
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
)
class MyPenaltyTicketViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for viewing current user's own penalty tickets.

    Provides read-only access to penalty tickets for the authenticated user.
    """

    queryset = PenaltyTicket.objects.all()
    serializer_class = PenaltyTicketSerializer
    permission_classes = [RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    filterset_class = PenaltyTicketFilterSet
    search_fields = ["code"]
    ordering_fields = ["created_at", "month", "amount", "status"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = _("Payroll")
    submodule = _("My Penalty Tickets")
    permission_prefix = "payroll.my_penalty_ticket"

    PERMISSIONS_REGISTERED_ACTIONS = {
        "list": {
            "name_template": _("List my penalty tickets"),
            "description_template": _("View list of my penalty tickets"),
        },
        "retrieve": {
            "name_template": _("View my penalty ticket"),
            "description_template": _("View detail of my penalty ticket"),
        },
    }

    def get_queryset(self):
        """Filter queryset to only show current user's penalty tickets."""
        user = self.request.user
        if not user or not user.is_authenticated:
            raise PermissionDenied(_("You need to login to perform this action"))

        employee = getattr(user, "employee", None)
        if not employee:
            raise PermissionDenied(_("You do not have an associated employee record"))

        return (
            super()
            .get_queryset()
            .filter(employee=employee)
            .select_related("employee", "created_by", "updated_by")
            .prefetch_related("attachments")
        )
