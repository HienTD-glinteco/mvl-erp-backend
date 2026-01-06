from rest_framework.routers import DefaultRouter

from apps.payroll.api.views import MyKPIAssessmentViewSet, MyPenaltyTicketViewSet, MyTeamKPIAssessmentViewSet

app_name = "payroll-mobile"

router = DefaultRouter()

# My Penalty tickets
router.register(r"me/penalty-tickets", MyPenaltyTicketViewSet, basename="my-penalty-ticket")

# My KPI assessments
router.register(r"me/kpi-assessments", MyKPIAssessmentViewSet, basename="my-kpi-assessment")

# Team KPI assessments (for managers)
router.register(r"me/team-kpi-assessments", MyTeamKPIAssessmentViewSet, basename="my-team-kpi-assessment")

urlpatterns = router.urls
