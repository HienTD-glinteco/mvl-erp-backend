from django.conf import settings
from django.contrib import admin
from django.core.cache import cache

from .models import (
    AdministrativeUnit,
    DeviceChangeRequest,
    MobileAppConfig,
    Nationality,
    PasswordResetOTP,
    Permission,
    Province,
    Role,
    User,
    UserDevice,
)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Admin configuration for Position model"""

    list_display = ["code", "name", "description", "module", "submodule"]
    list_filter = ["module"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "module", "submodule"]


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    """Admin configuration for Position model"""

    list_filter = ["client", "platform", "state"]
    list_display = ["user", "client", "platform", "state"]
    search_fields = ["device_id", "push_token", "user__username"]


class AdministrativeUnitInline(admin.TabularInline):
    model = AdministrativeUnit
    fk_name = "parent_province"
    extra = 0
    fields = ["code", "name", "level"]
    readonly_fields = ["code", "name", "level"]
    show_change_link = True


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]
    search_fields = ["code", "name"]
    inlines = [AdministrativeUnitInline]


class UserDeviceInline(admin.TabularInline):
    model = UserDevice
    fk_name = "user"
    extra = 0
    fields = ["client", "platform", "state", "device_id"]
    readonly_fields = ["client", "platform", "state", "device_id"]
    show_change_link = True


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["username", "email", "is_staff", "is_active"]
    search_fields = ["username", "email"]
    inlines = [UserDeviceInline]


@admin.register(MobileAppConfig)
class MobileAppConfigAdmin(admin.ModelAdmin):
    """Admin configuration for MobileAppConfig singleton"""

    list_display = [
        "ios_latest_version",
        "ios_min_supported_version",
        "android_latest_version",
        "android_min_supported_version",
        "maintenance_enabled",
        "updated_at",
    ]
    list_filter = ["maintenance_enabled"]
    search_fields = [
        "ios_latest_version",
        "ios_min_supported_version",
        "ios_store_url",
        "android_latest_version",
        "android_min_supported_version",
        "android_store_url",
        "links_terms_url",
        "links_privacy_url",
        "links_support_url",
        "feature_flags",
    ]
    readonly_fields = ["updated_at"]
    fieldsets = (
        ("iOS", {"fields": ("ios_latest_version", "ios_min_supported_version", "ios_store_url")}),
        ("Android", {"fields": ("android_latest_version", "android_min_supported_version", "android_store_url")}),
        ("Maintenance", {"fields": ("maintenance_enabled", "maintenance_message")}),
        ("Features", {"fields": ("feature_flags",)}),
        ("Links", {"fields": ("links_terms_url", "links_privacy_url", "links_support_url")}),
        ("Metadata", {"fields": ("updated_at",)}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete(settings.MOBILE_APP_CONFIG_CACHE_KEY)

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        cache.delete(settings.MOBILE_APP_CONFIG_CACHE_KEY)


admin.site.register(Role)
admin.site.register(PasswordResetOTP)
admin.site.register(AdministrativeUnit)
admin.site.register(Nationality)
admin.site.register(DeviceChangeRequest)
