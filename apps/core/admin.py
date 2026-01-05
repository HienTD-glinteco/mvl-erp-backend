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


admin.site.register(User)
admin.site.register(Role)
admin.site.register(PasswordResetOTP)
admin.site.register(Province)
admin.site.register(AdministrativeUnit)
admin.site.register(Nationality)
admin.site.register(DeviceChangeRequest)
