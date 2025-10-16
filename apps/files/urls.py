from django.urls import path

from .api.views import ConfirmFileUploadView, PresignURLView

app_name = "files"

urlpatterns = [
    path("presign/", PresignURLView.as_view(), name="presign"),
    path("confirm/", ConfirmFileUploadView.as_view(), name="confirm"),
]
