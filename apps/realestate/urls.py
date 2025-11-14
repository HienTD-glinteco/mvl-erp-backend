from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.realestate.api.views import ProjectViewSet

app_name = "realestate"

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")

urlpatterns = [
    path("", include(router.urls)),
]
