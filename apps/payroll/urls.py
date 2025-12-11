from django.urls import path

from apps.payroll.api.views import CurrentKPIConfigView, CurrentSalaryConfigView

app_name = "payroll"

urlpatterns = [
    path("salary-config/current/", CurrentSalaryConfigView.as_view(), name="salary-config-current"),
    path("kpi-config/current/", CurrentKPIConfigView.as_view(), name="kpi-config-current"),
]
