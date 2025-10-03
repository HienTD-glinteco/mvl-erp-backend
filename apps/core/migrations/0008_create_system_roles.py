# Generated manually

from django.db import migrations


def create_system_roles(apps, schema_editor):
    """Create default system roles VT001 and VT002"""
    Role = apps.get_model("core", "Role")
    Permission = apps.get_model("core", "Permission")

    # Create VT001 - Admin hệ thống
    admin_role, created = Role.objects.get_or_create(
        code="VT001",
        defaults={
            "name": "Admin hệ thống",
            "description": "Vai trò có tất cả các quyền của hệ thống",
            "is_system_role": True,
        },
    )
    if created:
        # Assign all permissions to admin role
        all_permissions = Permission.objects.all()
        admin_role.permissions.set(all_permissions)

    # Create VT002 - Vai trò cơ bản
    Role.objects.get_or_create(
        code="VT002",
        defaults={
            "name": "Vai trò cơ bản",
            "description": "Vai trò mặc định của tài khoản nhân viên khi được tạo mới",
            "is_system_role": True,
        },
    )


def reverse_system_roles(apps, schema_editor):
    """Remove default system roles"""
    Role = apps.get_model("core", "Role")
    Role.objects.filter(code__in=["VT001", "VT002"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_add_role_code_and_system_flag"),
    ]

    operations = [
        migrations.RunPython(create_system_roles, reverse_system_roles),
    ]
