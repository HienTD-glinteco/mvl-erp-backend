from django.contrib import admin

from .models import AdministrativeUnit, Nationality, PasswordResetOTP, Permission, Province, Role, User, UserDevice


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Admin configuration for Position model"""

    list_display = ["code", "name", "description", "module", "submodule"]
    list_filter = ["module"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "module", "submodule"]


admin.site.register(User)
admin.site.register(Role)
admin.site.register(PasswordResetOTP)
admin.site.register(UserDevice)
admin.site.register(Province)
admin.site.register(AdministrativeUnit)
admin.site.register(Nationality)
