"""
Demonstration script for the role-based permission system.

This script shows how to set up and use the permission system.
Run this in Django shell or as a management command.

Usage:
    python manage.py shell < docs/PERMISSIONS_DEMO.py
"""

from apps.core.models import Permission, Role, User

print("=" * 60)
print("Role-Based Permission System Demonstration")
print("=" * 60)

# Step 1: Create permissions
print("\n1. Creating permissions...")
document_view = Permission.objects.get_or_create(
    code="document.view",
    defaults={"description": "Xem tài liệu"},
)[0]
print(f"   ✓ Created: {document_view}")

document_create = Permission.objects.get_or_create(
    code="document.create",
    defaults={"description": "Tạo tài liệu"},
)[0]
print(f"   ✓ Created: {document_create}")

document_edit = Permission.objects.get_or_create(
    code="document.edit",
    defaults={"description": "Sửa tài liệu"},
)[0]
print(f"   ✓ Created: {document_edit}")

document_delete = Permission.objects.get_or_create(
    code="document.delete",
    defaults={"description": "Xóa tài liệu"},
)[0]
print(f"   ✓ Created: {document_delete}")

# Step 2: Create roles
print("\n2. Creating roles...")
viewer_role = Role.objects.get_or_create(
    name="Document Viewer",
    defaults={"description": "Người xem tài liệu"},
)[0]
viewer_role.permissions.clear()
viewer_role.permissions.add(document_view)
print(f"   ✓ Created: {viewer_role} with {viewer_role.permissions.count()} permission(s)")

editor_role = Role.objects.get_or_create(
    name="Document Editor",
    defaults={"description": "Người biên tập tài liệu"},
)[0]
editor_role.permissions.clear()
editor_role.permissions.add(document_view, document_create, document_edit)
print(f"   ✓ Created: {editor_role} with {editor_role.permissions.count()} permission(s)")

admin_role = Role.objects.get_or_create(
    name="Document Admin",
    defaults={"description": "Quản trị viên tài liệu"},
)[0]
admin_role.permissions.clear()
admin_role.permissions.add(document_view, document_create, document_edit, document_delete)
print(f"   ✓ Created: {admin_role} with {admin_role.permissions.count()} permission(s)")

# Step 3: Create test users
print("\n3. Creating test users...")
viewer_user = User.objects.get_or_create(
    username="viewer_user",
    defaults={
        "email": "viewer@example.com",
        "first_name": "View",
        "last_name": "User",
    },
)[0]
viewer_user.role = viewer_role
viewer_user.save()
print(f"   ✓ Created: {viewer_user} with role: {viewer_role.name}")

editor_user = User.objects.get_or_create(
    username="editor_user",
    defaults={
        "email": "editor@example.com",
        "first_name": "Edit",
        "last_name": "User",
    },
)[0]
editor_user.role = editor_role
editor_user.save()
print(f"   ✓ Created: {editor_user} with role: {editor_role.name}")

admin_user = User.objects.get_or_create(
    username="admin_user",
    defaults={
        "email": "admin@example.com",
        "first_name": "Admin",
        "last_name": "User",
    },
)[0]
admin_user.role = admin_role
admin_user.save()
print(f"   ✓ Created: {admin_user} with role: {admin_role.name}")

# Step 4: Test permissions
print("\n4. Testing permissions...")


def check_permission(user, permission_code):
    """Helper function to check and display permission"""
    has_perm = user.has_permission(permission_code)
    status = "✓ ALLOWED" if has_perm else "✗ DENIED"
    print(f"   {user.username:20} {permission_code:20} {status}")


print("\n   Permission Check Results:")
print("   " + "-" * 56)

# Test viewer user
print(f"\n   {viewer_user.username} (Viewer Role):")
check_permission(viewer_user, "document.view")
check_permission(viewer_user, "document.create")
check_permission(viewer_user, "document.edit")
check_permission(viewer_user, "document.delete")

# Test editor user
print(f"\n   {editor_user.username} (Editor Role):")
check_permission(editor_user, "document.view")
check_permission(editor_user, "document.create")
check_permission(editor_user, "document.edit")
check_permission(editor_user, "document.delete")

# Test admin user
print(f"\n   {admin_user.username} (Admin Role):")
check_permission(admin_user, "document.view")
check_permission(admin_user, "document.create")
check_permission(admin_user, "document.edit")
check_permission(admin_user, "document.delete")

# Step 5: Display summary
print("\n" + "=" * 60)
print("Summary:")
print("=" * 60)
print(f"Total Permissions: {Permission.objects.count()}")
print(f"Total Roles: {Role.objects.count()}")
print(f"Total Users with Roles: {User.objects.filter(roles__isnull=False).distinct().count()}")

print("\n" + "=" * 60)
print("Demo completed successfully!")
print("=" * 60)
print("\nNext steps:")
print("1. Add permission_prefix and action mapping via PermissionRegistrationMixin/PermissionedAPIView")
print("2. Run: python manage.py collect_permissions")
print("3. Ensure RoleBasedPermission is included in permission_classes")
print("4. Test your API endpoints!")
