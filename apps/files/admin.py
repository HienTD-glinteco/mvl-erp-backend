from django.contrib import admin

from .models import FileModel


@admin.register(FileModel)
class FileModelAdmin(admin.ModelAdmin):
    """Admin interface for FileModel."""

    list_display = ["id", "file_name", "purpose", "is_confirmed", "size", "created_at"]
    list_filter = ["purpose", "is_confirmed", "created_at"]
    search_fields = ["file_name", "purpose", "file_path"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            None,
            {
                "fields": ("purpose", "file_name", "file_path", "size", "checksum", "is_confirmed"),
            },
        ),
        (
            "Related Object",
            {
                "fields": ("content_type", "object_id"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
