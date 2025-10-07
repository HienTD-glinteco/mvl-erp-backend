from rest_framework.routers import DefaultRouter

from .api.views import NotificationViewSet

app_name = "notifications"

router = DefaultRouter()
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = router.urls
