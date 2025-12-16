from datetime import date

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import DepartmentKPIAssessmentFilterSet
from apps.payroll.api.serializers import (
    DepartmentKPIAssessmentListSerializer,
    DepartmentKPIAssessmentSerializer,
    DepartmentKPIAssessmentUpdateSerializer,
)
from apps.payroll.models import DepartmentKPIAssessment, KPIConfig
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List department KPI assessments",
        description="Retrieve a paginated list of department KPI assessments",
        tags=["10.4: Department KPI Assessments"],
        examples=[
            OpenApiExample(
                "Success - List of department assessments",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "period": 1,
                                "department": 1,
                                "department_name": "Sales Department",
                                "department_code": "PB001",
                                "month": "2025-12-01",
                                "kpi_config_snapshot": {},
                                "grade": "B",
                                "finalized": False,
                                "created_at": "2025-12-01T00:00:00Z",
                                "updated_at": "2025-12-01T00:00:00Z",
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
        summary="Get department KPI assessment details",
        description="Retrieve detailed information about a specific department KPI assessment",
        tags=["10.4: Department KPI Assessments"],
    ),
    partial_update=extend_schema(
        summary="Update department KPI assessment",
        description="Update grade or note for a department KPI assessment",
        tags=["10.4: Department KPI Assessments"],
        examples=[
            OpenApiExample(
                "Request - Update grade",
                value={"grade": "A", "note": "Excellent department performance"},
                request_only=True,
            ),
        ],
    ),
)
class DepartmentKPIAssessmentViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for DepartmentKPIAssessment model.

    Provides CRUD operations and custom actions for:
    - Generating department assessments
    - Auto-assigning grades to employees
    - Finalizing department assessments
    - Viewing assignment logs
    """

    queryset = DepartmentKPIAssessment.objects.select_related(
        "period",
        "department",
        "assigned_by",
        "created_by",
        "updated_by",
    )
    filterset_class = DepartmentKPIAssessmentFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["department__name", "department__code"]
    ordering_fields = ["period__month", "department__name", "grade", "created_at"]
    ordering = ["-period__month", "-created_at"]

    # Permission registration attributes
    module = "Payroll"
    submodule = "KPI Management"
    permission_prefix = "department_kpi_assessment"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return DepartmentKPIAssessmentListSerializer
        elif self.action in ["update", "partial_update"]:
            return DepartmentKPIAssessmentUpdateSerializer
        return DepartmentKPIAssessmentSerializer

    def perform_create(self, serializer):
        """Set created_by when creating."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set updated_by and assigned info when updating."""
        serializer.save(
            updated_by=self.request.user,
            assigned_by=self.request.user,
            assigned_at=timezone.now(),
        )

    @extend_schema(
        summary="Generate department KPI assessments",
        description="Generate default department KPI assessments for a specific month. Creates assessments with default grade 'C'.",
        tags=["10.4: Department KPI Assessments"],
        parameters=[
            OpenApiParameter(name="month", description="Month in YYYY-MM format", required=True, type=str),
            OpenApiParameter(
                name="department_ids", description="Comma-separated department IDs", required=False, type=str
            ),
        ],
        request=None,
        responses={200: DepartmentKPIAssessmentSerializer(many=True)},
    )
    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Generate department KPI assessments for a month."""
        month_str = request.query_params.get("month")
        department_ids_str = request.query_params.get("department_ids")

        if not month_str:
            return Response(
                {"detail": _("Month parameter is required (format: YYYY-MM)")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            year, month = map(int, month_str.split("-"))
            month_date = date(year, month, 1)
        except (ValueError, AttributeError):
            return Response(
                {"detail": _("Invalid month format. Use YYYY-MM")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get latest KPIConfig
        kpi_config = KPIConfig.objects.first()
        if not kpi_config:
            return Response(
                {"detail": _("No KPI configuration found")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get departments to generate for
        from apps.hrm.models import Department

        departments_qs = Department.objects.filter(is_active=True)
        if department_ids_str:
            try:
                department_ids = [int(x.strip()) for x in department_ids_str.split(",")]
                departments_qs = departments_qs.filter(id__in=department_ids)
            except ValueError:
                return Response(
                    {"detail": _("Invalid department_ids format")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        created_assessments = []
        skipped_count = 0

        with transaction.atomic():
            # Get or create the period
            from apps.payroll.models import KPIAssessmentPeriod

            period, created = KPIAssessmentPeriod.objects.get_or_create(
                month=month_date,
                defaults={
                    "kpi_config_snapshot": kpi_config.config,
                    "created_by": request.user,
                },
            )

            for department in departments_qs:
                # Check if assessment already exists
                if DepartmentKPIAssessment.objects.filter(department=department, period=period).exists():
                    skipped_count += 1
                    continue

                # Create assessment with default grade
                assessment = DepartmentKPIAssessment.objects.create(
                    period=period,
                    department=department,
                    grade="C",
                    default_grade="C",
                    created_by=request.user,
                )

                created_assessments.append(assessment)

        serializer = self.get_serializer(created_assessments, many=True)
        return Response(
            {
                "created": len(created_assessments),
                "skipped": skipped_count,
                "assessments": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Finalize department KPI assessment",
        description="Finalize department assessment. Use force=true to bypass validation (admin only).",
        tags=["10.4: Department KPI Assessments"],
        parameters=[
            OpenApiParameter(
                name="force", description="Force finalize even with violations", required=False, type=bool
            ),
        ],
        request=None,
        responses={200: DepartmentKPIAssessmentSerializer},
    )
    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        """Finalize a department assessment."""
        dept_assessment = self.get_object()

        if dept_assessment.finalized:
            return Response(
                {"detail": _("Assessment is already finalized")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        force = request.query_params.get("force", "false").lower() == "true"

        # Finalize
        dept_assessment.finalized = True
        dept_assessment.updated_by = request.user
        dept_assessment.save()

        serializer = DepartmentKPIAssessmentSerializer(dept_assessment)
        return Response({"message": _("Department assessment finalized successfully"), "assessment": serializer.data})
