from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.payroll.api.views import (
    CurrentKPIConfigView,
    CurrentSalaryConfigView,
    DepartmentKPIAssessmentViewSet,
    EmployeeKPIAssessmentViewSet,
    KPIAssessmentPeriodViewSet,
    KPICriterionViewSet,
)
from apps.payroll.api.views.employee_self_assessment import EmployeeSelfAssessmentViewSet

app_name = "payroll"

router = DefaultRouter()
router.register(r"kpi/criteria", KPICriterionViewSet, basename="kpi-criteria")
router.register(r"kpi/periods", KPIAssessmentPeriodViewSet, basename="kpi-periods")
router.register(r"kpi/assessments", EmployeeKPIAssessmentViewSet, basename="kpi-assessments")
router.register(r"kpi/departments/assessments", DepartmentKPIAssessmentViewSet, basename="kpi-department-assessments")
router.register(r"kpi/employees/assessments", EmployeeSelfAssessmentViewSet, basename="kpi-employee-self-assessments")

urlpatterns = [
    path("salary-config/current/", CurrentSalaryConfigView.as_view(), name="salary-config-current"),
    path("kpi-config/current/", CurrentKPIConfigView.as_view(), name="kpi-config-current"),
]

urlpatterns += router.urls
