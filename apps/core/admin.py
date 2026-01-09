from django.contrib import admin

from .models import (
    AdministrativeUnit,
    DeviceChangeRequest,
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


admin.site.register(Role)
admin.site.register(PasswordResetOTP)
admin.site.register(AdministrativeUnit)
admin.site.register(Nationality)
admin.site.register(DeviceChangeRequest)
