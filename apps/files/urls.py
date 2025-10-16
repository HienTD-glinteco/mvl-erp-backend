from django.urls import path

from .api.views import ConfirmFileUploadView, ConfirmMultipleFilesView, PresignURLView

app_name = "files"

urlpatterns = [
    path("presign/", PresignURLView.as_view(), name="presign"),
    path("confirm/", ConfirmFileUploadView.as_view(), name="confirm"),
    path("confirm-multiple/", ConfirmMultipleFilesView.as_view(), name="confirm-multiple"),
]
