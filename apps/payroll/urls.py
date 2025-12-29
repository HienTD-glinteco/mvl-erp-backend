from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.payroll.api.views import (
    CurrentKPIConfigView,
    CurrentSalaryConfigView,
    DepartmentKPIAssessmentViewSet,
    EmployeeKPIAssessmentViewSet,
    EmployeeSelfAssessmentViewSet,
    KPIAssessmentPeriodViewSet,
    KPICriterionViewSet,
    ManagerAssessmentViewSet,
    PayrollSlipViewSet,
    PenaltyTicketViewSet,
    RecoveryVoucherViewSet,
    SalaryPeriodNotReadySlipsView,
    SalaryPeriodReadySlipsView,
    SalaryPeriodViewSet,
    SalesRevenueViewSet,
    TravelExpenseViewSet,
)

app_name = "payroll"

router = DefaultRouter()
router.register(r"kpi-criteria", KPICriterionViewSet, basename="kpi-criteria")
router.register(r"kpi-periods", KPIAssessmentPeriodViewSet, basename="kpi-periods")
router.register(r"kpi-assessments/employees", EmployeeKPIAssessmentViewSet, basename="kpi-assessments")
router.register(r"kpi-assessments/departments", DepartmentKPIAssessmentViewSet, basename="kpi-department-assessments")
router.register(r"kpi-assessments/mine", EmployeeSelfAssessmentViewSet, basename="kpi-employee-self-assessments")
router.register(r"kpi-assessments/manager", ManagerAssessmentViewSet, basename="kpi-manager-assessments")
router.register(r"travel-expenses", TravelExpenseViewSet, basename="travel-expenses")
router.register(r"recovery-vouchers", RecoveryVoucherViewSet, basename="recovery-vouchers")
router.register(r"sales-revenues", SalesRevenueViewSet, basename="sales-revenues")
router.register(r"penalty-tickets", PenaltyTicketViewSet, basename="penalty-tickets")
router.register(r"salary-periods", SalaryPeriodViewSet, basename="salary-periods")
router.register(r"payroll-slips", PayrollSlipViewSet, basename="payroll-slips")

urlpatterns = [
    path("salary-config/", CurrentSalaryConfigView.as_view(), name="salary-config-current"),
    path("kpi-config/", CurrentKPIConfigView.as_view(), name="kpi-config-current"),
    path("salary-periods/<int:pk>/ready/", SalaryPeriodReadySlipsView.as_view(), name="salary-period-ready"),
    path(
        "salary-periods/<int:pk>/not-ready/", SalaryPeriodNotReadySlipsView.as_view(), name="salary-period-not-ready"
    ),
]

urlpatterns += router.urls
