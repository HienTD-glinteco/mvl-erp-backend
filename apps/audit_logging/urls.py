from rest_framework.routers import DefaultRouter

from .api import views

router = DefaultRouter()
router.register(r"", views.AuditLogViewSet, basename="audit_logs")

urlpatterns = router.urls
