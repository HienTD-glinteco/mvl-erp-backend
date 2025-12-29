"""Views for salary period ready/not-ready payroll slips."""

from django.db.models import Q
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils.permissions import register_permission
from apps.payroll.api.serializers import PayrollSlipListSerializer
from apps.payroll.models import PayrollSlip, SalaryPeriod
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.drf.pagination import PageNumberWithSizePagination


class SalaryPeriodReadySlipsView(GenericAPIView):
    """View for ready payroll slips."""

    queryset = PayrollSlip.objects.all()
    serializer_class = PayrollSlipListSerializer
    permission_classes = [RoleBasedPermission]
    pagination_class = PageNumberWithSizePagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, PhraseSearchFilter]
    filterset_fields = {
        "employee_code": ["exact", "icontains"],
        "employee_name": ["icontains"],
        "department_name": ["exact", "icontains"],
        "position_name": ["exact", "icontains"],
        "has_unpaid_penalty": ["exact"],
        "need_resend_email": ["exact"],
        "calculated_at": ["gte", "lte", "isnull"],
    }
    ordering_fields = [
        "code",
        "employee_code",
        "employee_name",
        "gross_income",
        "net_salary",
        "calculated_at",
    ]
    ordering = ["-calculated_at"]
    search_fields = ["employee_code", "employee_name", "code"]

    @extend_schema(
        summary="Get ready payroll slips",
        description=(
            "Get ready payroll slips based on period status:\n"
            "- ONGOING: Returns all READY slips from this period and all previous periods\n"
            "- COMPLETED: Returns all DELIVERED slips from this period only"
        ),
        tags=["10.6: Salary Periods"],
        responses={
            200: PayrollSlipListSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "Success - Ready slips",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "PS_202401_0001",
                                "employee_code": "E001",
                                "employee_name": "John Doe",
                                "department_name": "IT",
                                "position_name": "Developer",
                                "gross_income": "15000000.00",
                                "net_salary": "13500000.00",
                                "status": "READY",
                                "colored_status": {"value": "READY", "variant": "success"},
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @register_permission(
        "salary_period.list_ready",
        description=_("View ready payroll slips"),
        module=_("Payroll"),
        submodule=_("Salary Periods"),
        name=_("View Ready Payroll Slips"),
    )
    def get(self, request, pk):
        """Get ready payroll slips for a salary period."""
        try:
            period = SalaryPeriod.objects.get(pk=pk)
        except SalaryPeriod.DoesNotExist:
            return Response(
                {"detail": "Salary period not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if period.status == SalaryPeriod.Status.ONGOING:
            # Get all READY slips from this period and all previous periods
            queryset = PayrollSlip.objects.filter(
                Q(salary_period=period, status=PayrollSlip.Status.READY)
                | Q(salary_period__month__lt=period.month, status=PayrollSlip.Status.READY)
            ).select_related("employee", "salary_period")
        else:  # COMPLETED
            # Get all DELIVERED slips from this period only
            queryset = PayrollSlip.objects.filter(
                salary_period=period, status=PayrollSlip.Status.DELIVERED
            ).select_related("employee", "salary_period")

        # Apply filters, search, and ordering
        queryset = self.filter_queryset(queryset)

        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SalaryPeriodNotReadySlipsView(GenericAPIView):
    """View for not-ready payroll slips."""

    queryset = PayrollSlip.objects.all()
    serializer_class = PayrollSlipListSerializer
    permission_classes = [RoleBasedPermission]
    pagination_class = PageNumberWithSizePagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, PhraseSearchFilter]
    filterset_fields = {
        "employee_code": ["exact", "icontains"],
        "employee_name": ["icontains"],
        "department_name": ["exact", "icontains"],
        "position_name": ["exact", "icontains"],
        "has_unpaid_penalty": ["exact"],
        "need_resend_email": ["exact"],
        "calculated_at": ["gte", "lte", "isnull"],
    }
    ordering_fields = [
        "code",
        "employee_code",
        "employee_name",
        "gross_income",
        "net_salary",
        "calculated_at",
    ]
    ordering = ["-calculated_at"]
    search_fields = ["employee_code", "employee_name", "code"]

    @extend_schema(
        summary="Get not-ready payroll slips",
        description=(
            "Get not-ready payroll slips based on period status:\n"
            "- ONGOING: Returns all PENDING/HOLD slips from this period and all previous periods\n"
            "- COMPLETED: Returns all PENDING/HOLD slips from this period only"
        ),
        tags=["10.6: Salary Periods"],
        responses={
            200: PayrollSlipListSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "Success - Not ready slips",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 2,
                                "code": "PS_202401_0002",
                                "employee_code": "E002",
                                "employee_name": "Jane Smith",
                                "department_name": "HR",
                                "position_name": "Manager",
                                "gross_income": "20000000.00",
                                "net_salary": "18000000.00",
                                "status": "PENDING",
                                "colored_status": {"value": "PENDING", "variant": "warning"},
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @register_permission(
        "salary_period.list_not_ready",
        description=_("View not-ready payroll slips"),
        module=_("Payroll"),
        submodule=_("Salary Periods"),
        name=_("View Not-Ready Payroll Slips"),
    )
    def get(self, request, pk):
        """Get not-ready payroll slips for a salary period."""
        try:
            period = SalaryPeriod.objects.get(pk=pk)
        except SalaryPeriod.DoesNotExist:
            return Response(
                {"detail": "Salary period not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if period.status == SalaryPeriod.Status.ONGOING:
            # Get all PENDING/HOLD slips from this period and all previous periods
            queryset = PayrollSlip.objects.filter(
                Q(salary_period=period, status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD])
                | Q(
                    salary_period__month__lt=period.month,
                    status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD],
                )
            ).select_related("employee", "salary_period")
        else:  # COMPLETED
            # Get all PENDING/HOLD slips from this period only
            queryset = PayrollSlip.objects.filter(
                salary_period=period, status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD]
            ).select_related("employee", "salary_period")

        # Apply filters, search, and ordering
        queryset = self.filter_queryset(queryset)

        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
