from django.contrib import admin

from apps.hrm.models import RoleBlockScope, RoleBranchScope, RoleDepartmentScope

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


admin.site.register(PasswordResetOTP)
admin.site.register(AdministrativeUnit)
admin.site.register(Nationality)
admin.site.register(DeviceChangeRequest)


class RoleBranchScopeInline(admin.TabularInline):
    model = RoleBranchScope
    fk_name = "role"
    extra = 0
    fields = ["branch"]
    raw_id_fields = ["branch"]
    verbose_name = "Branch Scope"
    verbose_name_plural = "Branch Scopes"


class RoleBlockScopeInline(admin.TabularInline):
    model = RoleBlockScope
    fk_name = "role"
    extra = 0
    fields = ["block"]
    raw_id_fields = ["block"]
    verbose_name = "Block Scope"
    verbose_name_plural = "Block Scopes"


class RoleDepartmentScopeInline(admin.TabularInline):
    model = RoleDepartmentScope
    fk_name = "role"
    extra = 0
    fields = ["department"]
    raw_id_fields = ["department"]
    verbose_name = "Department Scope"
    verbose_name_plural = "Department Scopes"


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin configuration for Role model"""

    list_display = ["code", "name", "is_system_role", "is_default_role", "data_scope_level"]
    list_filter = ["is_system_role", "is_default_role", "data_scope_level"]
    search_fields = ["code", "name", "description"]
    readonly_fields = ["code", "created_at", "updated_at"]
    filter_horizontal = ["permissions"]
    inlines = [RoleBranchScopeInline, RoleBlockScopeInline, RoleDepartmentScopeInline]
    fieldsets = [
        (None, {"fields": ["code", "name", "description"]}),
        ("Permissions", {"fields": ["permissions"]}),
        ("Data Scope", {"fields": ["data_scope_level"]}),
        ("Settings", {"fields": ["is_system_role", "is_default_role"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]


@admin.register(RoleBranchScope)
class RoleBranchScopeAdmin(admin.ModelAdmin):
    """Admin configuration for RoleBranchScope model"""

    list_display = ["id", "role", "branch", "created_at"]
    list_filter = ["branch"]
    search_fields = ["role__code", "role__name", "branch__code", "branch__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["role", "branch"]


@admin.register(RoleBlockScope)
class RoleBlockScopeAdmin(admin.ModelAdmin):
    """Admin configuration for RoleBlockScope model"""

    list_display = ["id", "role", "block", "created_at"]
    list_filter = ["block"]
    search_fields = ["role__code", "role__name", "block__code", "block__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["role", "block"]


@admin.register(RoleDepartmentScope)
class RoleDepartmentScopeAdmin(admin.ModelAdmin):
    """Admin configuration for RoleDepartmentScope model"""

    list_display = ["id", "role", "department", "created_at"]
    list_filter = ["department"]
    search_fields = ["role__code", "role__name", "department__code", "department__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["role", "department"]
