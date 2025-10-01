from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.hrm.models import Branch, Block, Department, Position, OrganizationChart
from apps.hrm.api.serializers import (
    BranchSerializer,
    BlockSerializer,
    DepartmentSerializer,
    PositionSerializer,
    OrganizationChartSerializer,
    OrganizationChartDetailSerializer,
)
from apps.hrm.api.filtersets import (
    BranchFilterSet,
    BlockFilterSet,
    DepartmentFilterSet,
    PositionFilterSet,
    OrganizationChartFilterSet,
)


@extend_schema_view(
    list=extend_schema(
        summary="Danh sách chi nhánh",
        description="Lấy danh sách tất cả chi nhánh trong hệ thống",
        tags=["Chi nhánh"],
    ),
    create=extend_schema(
        summary="Tạo chi nhánh mới",
        description="Tạo một chi nhánh mới trong hệ thống",
        tags=["Chi nhánh"],
    ),
    retrieve=extend_schema(
        summary="Chi tiết chi nhánh",
        description="Lấy thông tin chi tiết của một chi nhánh",
        tags=["Chi nhánh"],
    ),
    update=extend_schema(
        summary="Cập nhật chi nhánh",
        description="Cập nhật thông tin chi nhánh",
        tags=["Chi nhánh"],
    ),
    partial_update=extend_schema(
        summary="Cập nhật một phần chi nhánh",
        description="Cập nhật một phần thông tin chi nhánh",
        tags=["Chi nhánh"],
    ),
    destroy=extend_schema(
        summary="Xóa chi nhánh",
        description="Xóa chi nhánh khỏi hệ thống",
        tags=["Chi nhánh"],
    ),
)
class BranchViewSet(viewsets.ModelViewSet):
    """ViewSet for Branch model"""

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filterset_class = BranchFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["code"]


@extend_schema_view(
    list=extend_schema(
        summary="Danh sách khối",
        description="Lấy danh sách tất cả khối trong hệ thống",
        tags=["Khối"],
    ),
    create=extend_schema(
        summary="Tạo khối mới",
        description="Tạo một khối mới trong hệ thống",
        tags=["Khối"],
    ),
    retrieve=extend_schema(
        summary="Chi tiết khối",
        description="Lấy thông tin chi tiết của một khối",
        tags=["Khối"],
    ),
    update=extend_schema(
        summary="Cập nhật khối",
        description="Cập nhật thông tin khối",
        tags=["Khối"],
    ),
    partial_update=extend_schema(
        summary="Cập nhật một phần khối",
        description="Cập nhật một phần thông tin khối",
        tags=["Khối"],
    ),
    destroy=extend_schema(
        summary="Xóa khối",
        description="Xóa khối khỏi hệ thống",
        tags=["Khối"],
    ),
)
class BlockViewSet(viewsets.ModelViewSet):
    """ViewSet for Block model"""

    queryset = Block.objects.select_related("branch").all()
    serializer_class = BlockSerializer
    filterset_class = BlockFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at", "block_type"]
    ordering = ["branch__code", "code"]


@extend_schema_view(
    list=extend_schema(
        summary="Danh sách phòng ban",
        description="Lấy danh sách tất cả phòng ban trong hệ thống",
        tags=["Phòng ban"],
    ),
    create=extend_schema(
        summary="Tạo phòng ban mới",
        description="Tạo một phòng ban mới trong hệ thống",
        tags=["Phòng ban"],
    ),
    retrieve=extend_schema(
        summary="Chi tiết phòng ban",
        description="Lấy thông tin chi tiết của một phòng ban",
        tags=["Phòng ban"],
    ),
    update=extend_schema(
        summary="Cập nhật phòng ban",
        description="Cập nhật thông tin phòng ban",
        tags=["Phòng ban"],
    ),
    partial_update=extend_schema(
        summary="Cập nhật một phần phòng ban",
        description="Cập nhật một phần thông tin phòng ban",
        tags=["Phòng ban"],
    ),
    destroy=extend_schema(
        summary="Xóa phòng ban",
        description="Xóa phòng ban khỏi hệ thống",
        tags=["Phòng ban"],
    ),
)
class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Department model"""

    queryset = Department.objects.select_related(
        "block__branch", "parent_department", "management_department"
    ).all()
    serializer_class = DepartmentSerializer
    filterset_class = DepartmentFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["block__code", "code"]

    @extend_schema(
        summary="Cây phòng ban",
        description="Lấy cấu trúc cây phòng ban theo khối",
        tags=["Phòng ban"],
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
        summary="Lấy chức năng theo loại khối",
        description="Lấy danh sách chức năng phòng ban có thể chọn theo loại khối",
        tags=["Phòng ban"],
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
                "functions": [
                    {"value": choice[0], "label": choice[1]} for choice in choices
                ],
            }
        )

    @extend_schema(
        summary="Lấy phòng ban quản lý có thể chọn",
        description="Lấy danh sách phòng ban có thể làm phòng ban quản lý",
        tags=["Phòng ban"],
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

        departments = Department.objects.filter(
            block_id=block_id, function=function, is_active=True
        ).select_related("block__branch")

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
        summary="Danh sách chức vụ",
        description="Lấy danh sách tất cả chức vụ trong hệ thống",
        tags=["Chức vụ"],
    ),
    create=extend_schema(
        summary="Tạo chức vụ mới",
        description="Tạo một chức vụ mới trong hệ thống",
        tags=["Chức vụ"],
    ),
    retrieve=extend_schema(
        summary="Chi tiết chức vụ",
        description="Lấy thông tin chi tiết của một chức vụ",
        tags=["Chức vụ"],
    ),
    update=extend_schema(
        summary="Cập nhật chức vụ",
        description="Cập nhật thông tin chức vụ",
        tags=["Chức vụ"],
    ),
    partial_update=extend_schema(
        summary="Cập nhật một phần chức vụ",
        description="Cập nhật một phần thông tin chức vụ",
        tags=["Chức vụ"],
    ),
    destroy=extend_schema(
        summary="Xóa chức vụ",
        description="Xóa chức vụ khỏi hệ thống",
        tags=["Chức vụ"],
    ),
)
class PositionViewSet(viewsets.ModelViewSet):
    """ViewSet for Position model"""

    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    filterset_class = PositionFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "level", "created_at"]
    ordering = ["level", "code"]


@extend_schema_view(
    list=extend_schema(
        summary="Danh sách sơ đồ tổ chức",
        description="Lấy danh sách tất cả bản ghi sơ đồ tổ chức",
        tags=["Sơ đồ tổ chức"],
    ),
    create=extend_schema(
        summary="Tạo bản ghi sơ đồ tổ chức",
        description="Tạo một bản ghi sơ đồ tổ chức mới",
        tags=["Sơ đồ tổ chức"],
    ),
    retrieve=extend_schema(
        summary="Chi tiết sơ đồ tổ chức",
        description="Lấy thông tin chi tiết của một bản ghi sơ đồ tổ chức",
        tags=["Sơ đồ tổ chức"],
    ),
    update=extend_schema(
        summary="Cập nhật sơ đồ tổ chức",
        description="Cập nhật thông tin sơ đồ tổ chức",
        tags=["Sơ đồ tổ chức"],
    ),
    partial_update=extend_schema(
        summary="Cập nhật một phần sơ đồ tổ chức",
        description="Cập nhật một phần thông tin sơ đồ tổ chức",
        tags=["Sơ đồ tổ chức"],
    ),
    destroy=extend_schema(
        summary="Xóa bản ghi sơ đồ tổ chức",
        description="Xóa bản ghi sơ đồ tổ chức khỏi hệ thống",
        tags=["Sơ đồ tổ chức"],
    ),
)
class OrganizationChartViewSet(viewsets.ModelViewSet):
    """ViewSet for OrganizationChart model"""

    queryset = OrganizationChart.objects.select_related(
        "employee", "position", "department__block__branch"
    ).all()
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
    ordering_fields = ["start_date", "created_at", "position__level"]
    ordering = ["position__level", "start_date"]

    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == "retrieve":
            return OrganizationChartDetailSerializer
        return super().get_serializer_class()

    @extend_schema(
        summary="Sơ đồ tổ chức theo cấu trúc",
        description="Lấy sơ đồ tổ chức theo cấu trúc phân cấp",
        tags=["Sơ đồ tổ chức"],
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

            hierarchy[dept_key]["positions"].append(
                OrganizationChartDetailSerializer(org_chart).data
            )

        # Sort positions by level within each department
        for dept_data in hierarchy.values():
            dept_data["positions"].sort(key=lambda x: x["position"]["level"])

        return Response(list(hierarchy.values()))

    @extend_schema(
        summary="Nhân viên theo phòng ban",
        description="Lấy danh sách nhân viên theo phòng ban",
        tags=["Sơ đồ tổ chức"],
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

        queryset = self.get_queryset().filter(
            department_id=department_id, is_active=True, end_date__isnull=True
        )

        serializer = OrganizationChartDetailSerializer(queryset, many=True)
        return Response(serializer.data)
