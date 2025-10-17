from django.urls import path

from .api.views import ConfirmMultipleFilesView, PresignURLView

app_name = "files"

urlpatterns = [
    path("presign/", PresignURLView.as_view(), name="presign"),
    path("confirm/", ConfirmMultipleFilesView.as_view(), name="confirm"),
]
