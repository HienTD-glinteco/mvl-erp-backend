from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging import AuditLoggingMixin
from apps.hrm.api.filtersets import (
    BlockFilterSet,
    BranchFilterSet,
    DepartmentFilterSet,
    OrganizationChartFilterSet,
    PositionFilterSet,
)
from apps.hrm.api.serializers import (
    BlockSerializer,
    BranchSerializer,
    DepartmentSerializer,
    OrganizationChartDetailSerializer,
    OrganizationChartSerializer,
    PositionSerializer,
)
from apps.hrm.models import Block, Branch, Department, OrganizationChart, Position
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all branches",
        description="Retrieve a list of all branches in the system",
        tags=["Branch"],
        examples=[
            OpenApiExample(
                "List branches success",
                description="Example response when listing branches",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "code": "CN001",
                                "name": "Chi nhánh Hà Nội",
                                "address": "123 Hoàng Quốc Việt, Cầu Giấy, Hà Nội",
                                "phone": "024-3456-7890",
                                "email": "hanoi@example.com",
                                "is_active": True,
                                "created_at": "2025-01-10T10:00:00Z",
                                "updated_at": "2025-01-10T10:00:00Z",
                            },
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440001",
                                "code": "CN002",
                                "name": "Chi nhánh TP.HCM",
                                "address": "456 Nguyễn Văn Linh, Quận 7, TP.HCM",
                                "phone": "028-9876-5432",
                                "email": "hcmc@example.com",
                                "is_active": True,
                                "created_at": "2025-01-11T14:30:00Z",
                                "updated_at": "2025-01-11T14:30:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new branch",
        description="Create a new branch in the system",
        tags=["Branch"],
        examples=[
            OpenApiExample(
                "Create branch request",
                description="Example request to create a new branch",
                value={"name": "Chi nhánh Đà Nẵng", "address": "789 Trần Phú, Hải Châu, Đà Nẵng", "phone": "0236-1234-567", "email": "danang@example.com", "is_active": True},
                request_only=True,
            ),
            OpenApiExample(
                "Create branch success",
                description="Success response when creating a branch",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440003",
                        "code": "CN003",
                        "name": "Chi nhánh Đà Nẵng",
                        "address": "789 Trần Phú, Hải Châu, Đà Nẵng",
                        "phone": "0236-1234-567",
                        "email": "danang@example.com",
                        "is_active": True,
                        "created_at": "2025-01-15T09:20:00Z",
                        "updated_at": "2025-01-15T09:20:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get branch details",
        description="Retrieve detailed information about a specific branch",
        tags=["Branch"],
        examples=[
            OpenApiExample(
                "Get branch success",
                description="Example response when retrieving a branch",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "code": "CN001",
                        "name": "Chi nhánh Hà Nội",
                        "address": "123 Hoàng Quốc Việt, Cầu Giấy, Hà Nội",
                        "phone": "024-3456-7890",
                        "email": "hanoi@example.com",
                        "is_active": True,
                        "created_at": "2025-01-10T10:00:00Z",
                        "updated_at": "2025-01-10T10:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update branch",
        description="Update branch information",
        tags=["Branch"],
        examples=[
            OpenApiExample(
                "Update branch request",
                description="Example request to update a branch",
                value={"name": "Chi nhánh Hà Nội - Cập nhật", "address": "123 Hoàng Quốc Việt, Cầu Giấy, Hà Nội", "phone": "024-3456-7899", "email": "hanoi@example.com", "is_active": True},
                request_only=True,
            ),
            OpenApiExample(
                "Update branch success",
                description="Success response when updating a branch",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "code": "CN001",
                        "name": "Chi nhánh Hà Nội - Cập nhật",
                        "address": "123 Hoàng Quốc Việt, Cầu Giấy, Hà Nội",
                        "phone": "024-3456-7899",
                        "email": "hanoi@example.com",
                        "is_active": True,
                        "created_at": "2025-01-10T10:00:00Z",
                        "updated_at": "2025-01-16T11:45:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update branch",
        description="Partially update branch information",
        tags=["Branch"],
        examples=[
            OpenApiExample(
                "Partial update request",
                description="Example request to partially update a branch",
                value={"phone": "024-3456-7891"},
                request_only=True,
            ),
            OpenApiExample(
                "Partial update success",
                description="Success response when partially updating a branch",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "code": "CN001",
                        "name": "Chi nhánh Hà Nội",
                        "address": "123 Hoàng Quốc Việt, Cầu Giấy, Hà Nội",
                        "phone": "024-3456-7891",
                        "email": "hanoi@example.com",
                        "is_active": True,
                        "created_at": "2025-01-10T10:00:00Z",
                        "updated_at": "2025-01-16T13:20:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete branch",
        description="Remove a branch from the system",
        tags=["Branch"],
        examples=[
            OpenApiExample(
                "Delete branch success",
                description="Success response when deleting a branch",
                value=None,
                response_only=True,
                status_codes=["204"],
            )
        ],
    ),
)
class BranchViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Branch model"""

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filterset_class = BranchFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["code"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Organization"
    permission_prefix = "branch"


@extend_schema_view(
    list=extend_schema(
        summary="List all blocks",
        description="Retrieve a list of all blocks in the system",
        tags=["Block"],
    ),
    create=extend_schema(
        summary="Create a new block",
        description="Create a new block in the system",
        tags=["Block"],
    ),
    retrieve=extend_schema(
        summary="Get block details",
        description="Retrieve detailed information about a specific block",
        tags=["Block"],
    ),
    update=extend_schema(
        summary="Update block",
        description="Update block information",
        tags=["Block"],
    ),
    partial_update=extend_schema(
        summary="Partially update block",
        description="Partially update block information",
        tags=["Block"],
    ),
    destroy=extend_schema(
        summary="Delete block",
        description="Remove a block from the system",
        tags=["Block"],
    ),
)
class BlockViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Block model"""

    queryset = Block.objects.select_related("branch").all()
    serializer_class = BlockSerializer
    filterset_class = BlockFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at", "block_type"]
    ordering = ["branch__code", "code"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Organization"
    permission_prefix = "block"


@extend_schema_view(
    list=extend_schema(
        summary="List all departments",
        description="Retrieve a list of all departments in the system",
        tags=["Department"],
    ),
    create=extend_schema(
        summary="Create a new department",
        description="Create a new department in the system",
        tags=["Department"],
    ),
    retrieve=extend_schema(
        summary="Get department details",
        description="Retrieve detailed information about a specific department",
        tags=["Department"],
    ),
    update=extend_schema(
        summary="Update department",
        description="Update department information",
        tags=["Department"],
    ),
    partial_update=extend_schema(
        summary="Partially update department",
        description="Partially update department information",
        tags=["Department"],
    ),
    destroy=extend_schema(
        summary="Delete department",
        description="Remove a department from the system",
        tags=["Department"],
    ),
)
class DepartmentViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Department model"""

    queryset = Department.objects.select_related("block__branch", "parent_department", "management_department").all()
    serializer_class = DepartmentSerializer
    filterset_class = DepartmentFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["block__code", "code"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Organization"
    permission_prefix = "department"

    @extend_schema(
        summary="Department tree structure",
        description="Retrieve department tree structure by block",
        tags=["Department"],
    )
    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Get department tree structure"""
        block_id = request.query_params.get("block_id")

        if block_id:
            departments = self.queryset.filter(block_id=block_id, is_active=True)
        else:
            departments = self.queryset.filter(is_active=True)

        # Build tree structure
        tree = []
        department_dict = {}

        # First pass: create all nodes
        for dept in departments:
            serialized = self.get_serializer(dept).data
            serialized["children"] = []
            department_dict[dept.id] = serialized

        # Second pass: build tree
        for dept in departments:
            if dept.parent_department_id:
                parent = department_dict.get(dept.parent_department_id)
                if parent:
                    parent["children"].append(department_dict[dept.id])
            else:
                tree.append(department_dict[dept.id])

        return Response(tree)

    @extend_schema(
        summary="Get department functions by block type",
        description="Retrieve available department functions based on block type",
        tags=["Department"],
    )
    @action(detail=False, methods=["get"])
    def function_choices(self, request):
        """Get function choices based on block type"""
        block_type = request.query_params.get("block_type")

        if not block_type:
            return Response(
                {"error": "block_type parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        choices = Department.get_function_choices_for_block_type(block_type)
        return Response(
            {
                "block_type": block_type,
                "functions": [{"value": choice[0], "label": choice[1]} for choice in choices],
            }
        )

    @extend_schema(
        summary="Get available management departments",
        description="Retrieve departments that can serve as management departments",
        tags=["Department"],
    )
    @action(detail=False, methods=["get"])
    def management_choices(self, request):
        """Get available management departments"""
        block_id = request.query_params.get("block_id")
        function = request.query_params.get("function")

        if not all([block_id, function]):
            return Response(
                {"error": "block_id and function parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        departments = Department.objects.filter(block_id=block_id, function=function, is_active=True).select_related(
            "block__branch"
        )

        choices = [
            {
                "id": str(dept.id),
                "name": dept.name,
                "code": dept.code,
                "full_path": f"{dept.block.branch.name}/{dept.block.name}/{dept.name}",
            }
            for dept in departments
        ]

        return Response(choices)


@extend_schema_view(
    list=extend_schema(
        summary="List all positions",
        description="Retrieve a list of all positions in the system",
        tags=["Position"],
    ),
    create=extend_schema(
        summary="Create a new position",
        description="Create a new position in the system",
        tags=["Position"],
    ),
    retrieve=extend_schema(
        summary="Get position details",
        description="Retrieve detailed information about a specific position",
        tags=["Position"],
    ),
    update=extend_schema(
        summary="Update position",
        description="Update position information",
        tags=["Position"],
    ),
    partial_update=extend_schema(
        summary="Partially update position",
        description="Partially update position information",
        tags=["Position"],
    ),
    destroy=extend_schema(
        summary="Delete position",
        description="Remove a position from the system",
        tags=["Position"],
    ),
)
class PositionViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Position model"""

    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    filterset_class = PositionFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["name", "code"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Organization"
    permission_prefix = "position"


@extend_schema_view(
    list=extend_schema(
        summary="List organization charts",
        description="Retrieve a list of all organization charts",
        tags=["Organization Chart"],
    ),
    create=extend_schema(
        summary="Create organization chart",
        description="Create a new organization chart",
        tags=["Organization Chart"],
    ),
    retrieve=extend_schema(
        summary="Get organization chart details",
        description="Retrieve detailed information about a specific organization chart",
        tags=["Organization Chart"],
    ),
    update=extend_schema(
        summary="Update organization chart",
        description="Update organization chart information",
        tags=["Organization Chart"],
    ),
    partial_update=extend_schema(
        summary="Partially update organization chart",
        description="Partially update organization chart information",
        tags=["Organization Chart"],
    ),
    destroy=extend_schema(
        summary="Delete organization chart",
        description="Remove an organization chart from the system",
        tags=["Organization Chart"],
    ),
)
class OrganizationChartViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for OrganizationChart model"""

    queryset = OrganizationChart.objects.select_related("employee", "position", "department__block__branch").all()
    serializer_class = OrganizationChartSerializer
    filterset_class = OrganizationChartFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "employee__username",
        "employee__first_name",
        "employee__last_name",
        "position__name",
        "department__name",
    ]
    ordering_fields = ["start_date", "created_at", "position__name"]
    ordering = ["position__name", "start_date"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Organization"
    permission_prefix = "organization_chart"

    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == "retrieve":
            return OrganizationChartDetailSerializer
        return super().get_serializer_class()

    @extend_schema(
        summary="Organization chart hierarchy",
        description="Retrieve organization chart in hierarchical structure",
        tags=["Organization Chart"],
    )
    @action(detail=False, methods=["get"])
    def hierarchy(self, request):
        """Get organization chart in hierarchical structure"""
        branch_id = request.query_params.get("branch_id")
        block_id = request.query_params.get("block_id")
        department_id = request.query_params.get("department_id")

        queryset = self.get_queryset().filter(is_active=True, end_date__isnull=True)

        if branch_id:
            queryset = queryset.filter(department__block__branch_id=branch_id)
        if block_id:
            queryset = queryset.filter(department__block_id=block_id)
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        # Group by department
        hierarchy = {}
        for org_chart in queryset:
            dept_key = f"{org_chart.department.id}"
            if dept_key not in hierarchy:
                hierarchy[dept_key] = {
                    "department": DepartmentSerializer(org_chart.department).data,
                    "positions": [],
                }

            hierarchy[dept_key]["positions"].append(OrganizationChartDetailSerializer(org_chart).data)

        # Sort positions by name within each department
        for dept_data in hierarchy.values():
            dept_data["positions"].sort(key=lambda x: x["position"]["name"])

        return Response(list(hierarchy.values()))

    @extend_schema(
        summary="Employees by department",
        description="Retrieve list of employees by department",
        tags=["Organization Chart"],
    )
    @action(detail=False, methods=["get"])
    def by_department(self, request):
        """Get employees by department"""
        department_id = request.query_params.get("department_id")
        if not department_id:
            return Response(
                {"error": "department_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(department_id=department_id, is_active=True, end_date__isnull=True)

        serializer = OrganizationChartDetailSerializer(queryset, many=True)
        return Response(serializer.data)
