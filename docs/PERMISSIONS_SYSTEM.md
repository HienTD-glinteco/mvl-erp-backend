# Django Role-Based Permission System

## Overview

This document describes the role-based permission system implemented for the MaiVietLand backend. The system provides a flexible, decorator-based approach to managing API permissions through roles and permissions.

> **Note (2025-12):** The legacy `@register_permission` decorator has been removed. New endpoints should inherit from `PermissionRegistrationMixin`-based classes (e.g., `BaseModelViewSet`, `PermissionedAPIView`) and define `permission_prefix` plus `permission_action_map`.

## Architecture

### Database Schema

```
User (Django User Model)
  └─── ManyToMany ───> Role
                         └─── ManyToMany ───> Permission

User.has_permission(code) -> checks through all assigned roles
```

### Models

#### Permission (`apps/core/models/permission.py`)
- **code** (CharField, unique): Unique identifier for the permission (e.g., "document.create")
- **description** (CharField): Human-readable description in Vietnamese
- **created_at**: Timestamp when permission was created
- **updated_at**: Timestamp when permission was last updated

#### Role (`apps/core/models/role.py`)
- **name** (CharField, unique): Role name (e.g., "Editor", "Manager")
- **description** (CharField): Role description
- **permissions** (ManyToMany): Permissions assigned to this role
- **created_at**: Timestamp when role was created
- **updated_at**: Timestamp when role was last updated

#### User Extensions (`apps/core/models/user.py`)
- **roles** (ManyToMany): Roles assigned to the user
- **has_permission(code)**: Method to check if user has a specific permission

### Components

#### 1. Legacy @register_permission Decorator (removed)

**Purpose**: Mark views with permission requirements

**Signature**: `@register_permission(code: str, description: str)`

**How it works**:
- Attaches `_permission_code` and `_permission_description` attributes to the view function/method
- These attributes are read by both `RoleBasedPermission` and `collect_permissions` command
- Does not perform any validation itself - purely metadata attachment

**Usage**:
```python
from apps.core.utils import register_permission

@api_view(["POST"])
@register_permission("document.create", "Tạo tài liệu")
def document_create(request):
    pass
```

#### 2. RoleBasedPermission Class (`apps/core/api/permissions.py`)

**Purpose**: DRF permission class that enforces role-based permissions

**How it works**:
1. Extracts `_permission_code` from the view
2. If no code is found, allows access (view doesn't require permission)
3. Checks if user is authenticated
4. Checks if user is a superuser (always allowed)
5. Calls `user.has_permission(code)` to verify access through roles
6. Raises `PermissionDenied` with appropriate message if access is denied

**Integration**: Add to `permission_classes` in views

#### 3. collect_permissions Management Command (`apps/core/management/commands/collect_permissions.py`)

**Purpose**: Automatically discover and sync permissions from code to database

**How it works**:
1. Gets all URL patterns from Django's URL resolver
2. Recursively traverses nested URLconfs
3. For each pattern, extracts the view callback
4. Checks for `_permission_code` attribute on:
   - Function-based views
   - Class-based view methods (get, post, etc.)
   - ViewSet actions (list, create, etc.)
   - Custom ViewSet actions decorated with `@action`
5. Uses `update_or_create` to sync to database
6. Reports statistics on created/updated permissions

**Usage**: `python manage.py collect_permissions`

## Implementation Details

### Permission Checking Flow

```
1. Request arrives at view
2. DRF calls RoleBasedPermission.has_permission()
3. Extract permission_code from view metadata
4. If no code: ALLOW (view doesn't require permission)
5. If user not authenticated: DENY with "Bạn cần đăng nhập"
6. If user is superuser: ALLOW
7. Call user.has_permission(code)
   - Queries: User -> roles -> permissions
   - Returns True if any role has the permission
8. If True: ALLOW
9. If False: DENY with "Bạn không có quyền"
```

### Database Queries

The `has_permission` method uses an optimized query:
```python
def has_permission(self, permission_code: str) -> bool:
    if self.is_superuser:
        return True
    return self.roles.filter(permissions__code=permission_code).exists()
```

This performs a single JOIN query:
```sql
SELECT EXISTS(
  SELECT 1 FROM core_role_permissions
  INNER JOIN core_user_roles ON ...
  WHERE permission_code = 'document.create'
  AND user_id = <user_id>
)
```

### URL Pattern Scanning

The `collect_permissions` command handles various Django URL patterns:

1. **Simple function views**: `path("api/document/", document_view)`
2. **Class-based views**: `path("api/document/", DocumentView.as_view())`
3. **ViewSets with routers**: `router.register("documents", DocumentViewSet)`
4. **Nested URLs**: `path("api/", include("app.urls"))`

## Migration

The system was added in migration `0005_add_permission_and_role_models.py`:

```python
# Creates:
- core_permission table
- core_role table
- core_role_permissions (ManyToMany join table)
- core_user_roles (ManyToMany join table)
```

## Testing

The system includes 20 comprehensive tests (`apps/core/tests/test_permissions.py`):

### Test Coverage
- **Model tests**: Permission and Role creation, relationships
- **User permission tests**: has_permission method, superuser bypass
- **Decorator tests**: Metadata attachment, function preservation
- **Permission class tests**: Allow/deny scenarios, class-based views
- **Command tests**: Permission collection, update behavior

### Running Tests
```bash
# Run all permission tests
python manage.py test apps.core.tests.test_permissions

# Run with verbosity
python manage.py test apps.core.tests.test_permissions -v 2
```

## Usage Examples

### Example 1: Simple API Endpoint

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils import register_permission

@api_view(["GET"])
@permission_classes([RoleBasedPermission])
@register_permission("report.view", "Xem báo cáo")
def view_report(request):
    return Response({"report": "data"})
```

### Example 2: ViewSet with Multiple Permissions

```python
from rest_framework import viewsets
from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils import register_permission

class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [RoleBasedPermission]

    @register_permission("document.list", "Xem danh sách tài liệu")
    def list(self, request):
        # Only users with document.list permission can access
        pass

    @register_permission("document.create", "Tạo tài liệu")
    def create(self, request):
        # Only users with document.create permission can access
        pass
```

### Example 3: Setting Up Roles

```python
from apps.core.models import Permission, Role, User

# Create permissions (usually done via collect_permissions command)
view_perm = Permission.objects.create(
    code="document.view",
    description="Xem tài liệu"
)
edit_perm = Permission.objects.create(
    code="document.edit",
    description="Sửa tài liệu"
)

# Create role and assign permissions
viewer_role = Role.objects.create(
    name="Document Viewer",
    description="Người xem tài liệu"
)
viewer_role.permissions.add(view_perm)

editor_role = Role.objects.create(
    name="Document Editor",
    description="Người biên tập tài liệu"
)
editor_role.permissions.add(view_perm, edit_perm)

# Assign role to user
user = User.objects.get(username="john")
user.role = editor_role
user.save()

# Check permissions
user.has_permission("document.view")  # True
user.has_permission("document.edit")  # True
user.has_permission("document.delete")  # False
```

## Best Practices

### 1. Permission Code Naming
Use dot notation with resource and action:
- ✅ `document.create`, `user.delete`, `report.view`
- ❌ `create_document`, `delete-user`, `viewReport`

### 2. Description Language
Always write descriptions in Vietnamese:
- ✅ `"Tạo tài liệu"`, `"Xóa người dùng"`
- ❌ `"Create document"`, `"Delete user"`

### 3. Granularity
Keep permissions granular but not excessive:
- ✅ `document.create`, `document.edit`, `document.delete`
- ❌ `document.create.draft`, `document.create.final` (too granular)
- ❌ `document.manage` (too broad)

### 4. Role Design
- Create roles based on job functions, not individuals
- Group related permissions into roles
- Avoid creating too many specialized roles

### 5. Superuser Usage
- Superusers bypass ALL permission checks
- Use sparingly - only for system administrators
- For high-privilege users, use roles instead

## Troubleshooting

### Issue: Permission not found in database
**Solution**: Run `python manage.py collect_permissions`

### Issue: User has role but still denied access
**Check**:
1. Does the role have the permission? `role.permissions.all()`
2. Is the permission code correct? Check for typos
3. Is the user assigned to the role? `user.roles.all()`

### Issue: Decorator not working
**Check**:
1. Is `RoleBasedPermission` in `permission_classes`?
2. Is the decorator on the correct method (for CBV/ViewSets)?
3. Run `collect_permissions` to ensure it's in the database

### Issue: All users being denied
**Check**:
1. Is `IsAuthenticated` also in `permission_classes`? (It should be)
2. Are users actually authenticated?
3. Check the view's `permission_classes` attribute

## Future Enhancements

Possible improvements to consider:

1. **Permission caching**: Cache user permissions to reduce database queries
2. **Permission groups**: Add intermediate grouping between roles and permissions
3. **Audit logging**: Log permission checks and access attempts
4. **UI for management**: Django admin integration or custom UI
5. **Permission inheritance**: Allow roles to inherit from other roles
6. **Dynamic permissions**: Support for object-level permissions

## Migration Guide

If you have existing views, follow these steps:

1. Add the decorator to views:
   ```python
   @register_permission("resource.action", "Description")
   ```

2. Run migrations:
   ```bash
   python manage.py migrate
   ```

3. Collect permissions:
   ```bash
   python manage.py collect_permissions
   ```

4. Create roles and assign permissions (via Django admin or script)

5. Assign roles to users

6. Add `RoleBasedPermission` to view `permission_classes`

7. Test thoroughly!

## References

- DRF Permissions: https://www.django-rest-framework.org/api-guide/permissions/
- Django User Model: https://docs.djangoproject.com/en/stable/ref/contrib/auth/
- URL Resolver: https://docs.djangoproject.com/en/stable/ref/urlresolvers/
