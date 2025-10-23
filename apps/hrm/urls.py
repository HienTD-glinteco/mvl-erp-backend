from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.hrm.api.views import (
    BlockViewSet,
    BranchViewSet,
    ContractTypeViewSet,
    DepartmentViewSet,
    EmployeeRoleViewSet,
    EmployeeViewSet,
    InterviewCandidateViewSet,
    InterviewScheduleViewSet,
    JobDescriptionViewSet,
    OrganizationChartViewSet,
    PositionViewSet,
    RecruitmentCandidateContactLogViewSet,
    RecruitmentCandidateViewSet,
    RecruitmentChannelViewSet,
    RecruitmentExpenseViewSet,
    RecruitmentRequestViewSet,
    RecruitmentSourceViewSet,
)

app_name = "hrm"

router = DefaultRouter()
router.register(r"branches", BranchViewSet, basename="branch")
router.register(r"blocks", BlockViewSet, basename="block")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"positions", PositionViewSet, basename="position")
router.register(r"organization-chart", OrganizationChartViewSet, basename="organization-chart")
router.register(r"employee-roles", EmployeeRoleViewSet, basename="employee-role")
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"contract-types", ContractTypeViewSet, basename="contract-type")
router.register(r"recruitment-channels", RecruitmentChannelViewSet, basename="recruitment-channel")
router.register(r"recruitment-sources", RecruitmentSourceViewSet, basename="recruitment-source")
router.register(r"job-descriptions", JobDescriptionViewSet, basename="job-description")
router.register(r"recruitment-requests", RecruitmentRequestViewSet, basename="recruitment-request")
router.register(r"recruitment-candidates", RecruitmentCandidateViewSet, basename="recruitment-candidate")
router.register(
    r"recruitment-candidate-contact-logs",
    RecruitmentCandidateContactLogViewSet,
    basename="recruitment-candidate-contact-log",
)
router.register(r"recruitment-expenses", RecruitmentExpenseViewSet, basename="recruitment-expense")
router.register(r"interview-schedules", InterviewScheduleViewSet, basename="interview-schedule")
router.register(r"interview-candidates", InterviewCandidateViewSet, basename="interview-candidate")

urlpatterns = [
    path("", include(router.urls)),
]
