from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.hrm.api.views import (
    AttendanceDeviceViewSet,
    AttendanceRecordViewSet,
    BlockViewSet,
    BranchViewSet,
    ContractTypeViewSet,
    DepartmentViewSet,
    EmployeeCertificateViewSet,
    EmployeeDependentViewSet,
    EmployeeRelationshipViewSet,
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
    RecruitmentDashboardViewSet,
    RecruitmentExpenseViewSet,
    RecruitmentReportsViewSet,
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
router.register(r"employee-certificates", EmployeeCertificateViewSet, basename="employee-certificate")
router.register(r"employee-dependents", EmployeeDependentViewSet, basename="employee-dependent")
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
router.register(r"employee-relationships", EmployeeRelationshipViewSet, basename="employee-relationship")
router.register(r"attendance-devices", AttendanceDeviceViewSet, basename="attendance-device")
router.register(r"attendance-records", AttendanceRecordViewSet, basename="attendance-record")

# Report endpoints (single ViewSet with custom actions)
router.register(r"reports", RecruitmentReportsViewSet, basename="recruitment-reports")

# Dashboard endpoints (single ViewSet with custom actions)
router.register(r"dashboard", RecruitmentDashboardViewSet, basename="recruitment-dashboard")

urlpatterns = [
    path("", include(router.urls)),
]
