"""URL patterns for mail templates API."""

from django.urls import path

from . import views

app_name = "mailtemplates"

urlpatterns = [
    # Template management
    path("", views.list_templates, name="list"),
    path("<str:slug>/", views.get_template, name="detail"),
    path("<str:slug>/save/", views.save_template, name="save"),
    path("<str:slug>/preview/", views.preview_template, name="preview"),
    # Sending
    path("<str:slug>/send/", views.send_bulk_email, name="send"),
    path("send/<uuid:job_id>/status/", views.get_send_job_status, name="send-status"),
]
