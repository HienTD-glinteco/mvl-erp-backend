from django.urls import path

from apps.payroll.api.views import CurrentSalaryConfigView

app_name = "payroll"

urlpatterns = [
    path("salary-config/current/", CurrentSalaryConfigView.as_view(), name="salary-config-current"),
]
