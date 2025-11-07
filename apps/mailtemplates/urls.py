"""URL patterns for mail templates API."""

from rest_framework.routers import DefaultRouter

from . import views

app_name = "mailtemplates"

router = DefaultRouter()
router.register(r"", views.MailTemplateViewSet, basename="mailtemplate")

urlpatterns = router.urls
