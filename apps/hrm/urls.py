from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.hrm.api.views import (
    BlockViewSet,
    BranchViewSet,
    DepartmentViewSet,
    OrganizationChartViewSet,
    PositionViewSet,
)

app_name = "hrm"

router = DefaultRouter()
router.register(r"branches", BranchViewSet, basename="branch")
router.register(r"blocks", BlockViewSet, basename="block")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"positions", PositionViewSet, basename="position")
router.register(r"organization-chart", OrganizationChartViewSet, basename="organization-chart")

urlpatterns = [
    path("", include(router.urls)),
]
