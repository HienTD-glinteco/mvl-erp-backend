"""Mobile URL configuration for payroll app."""

from rest_framework.routers import DefaultRouter

from apps.payroll.api.views import MyPenaltyTicketViewSet

app_name = "payroll"

router = DefaultRouter()
router.register(r"me/penalty-tickets", MyPenaltyTicketViewSet, basename="my-penalty-ticket")

urlpatterns = router.urls
