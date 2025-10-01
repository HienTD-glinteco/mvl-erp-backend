from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.hrm.api.views import (
    BranchViewSet,
    BlockViewSet,
    DepartmentViewSet,
    PositionViewSet,
    OrganizationChartViewSet,
)

app_name = "hrm"

router = DefaultRouter()
router.register(r"branches", BranchViewSet, basename="branch")
router.register(r"blocks", BlockViewSet, basename="block")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"positions", PositionViewSet, basename="position")
router.register(
    r"organization-chart", OrganizationChartViewSet, basename="organization-chart"
)

urlpatterns = [
    path("", include(router.urls)),
]
