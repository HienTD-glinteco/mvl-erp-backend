from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.payroll.api.views import CurrentKPIConfigView, CurrentSalaryConfigView, KPICriterionViewSet

app_name = "payroll"

router = DefaultRouter()
router.register(r"kpi/criteria", KPICriterionViewSet, basename="kpi-criteria")

urlpatterns = [
    path("salary-config/current/", CurrentSalaryConfigView.as_view(), name="salary-config-current"),
    path("kpi-config/current/", CurrentKPIConfigView.as_view(), name="kpi-config-current"),
]

urlpatterns += router.urls
