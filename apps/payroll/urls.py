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
)

app_name = "payroll"

router = DefaultRouter()
router.register(r"kpi-criteria", KPICriterionViewSet, basename="kpi-criteria")
router.register(r"kpi-periods", KPIAssessmentPeriodViewSet, basename="kpi-periods")
router.register(r"kpi-assessments/employees", EmployeeKPIAssessmentViewSet, basename="kpi-assessments")
router.register(r"kpi-assessments/departments", DepartmentKPIAssessmentViewSet, basename="kpi-department-assessments")
router.register(r"kpi-assessments/mine", EmployeeSelfAssessmentViewSet, basename="kpi-employee-self-assessments")
router.register(r"kpi-assessments/manager", ManagerAssessmentViewSet, basename="kpi-manager-assessments")

urlpatterns = [
    path("salary-config/", CurrentSalaryConfigView.as_view(), name="salary-config-current"),
    path("kpi-config/", CurrentKPIConfigView.as_view(), name="kpi-config-current"),
]

urlpatterns += router.urls
