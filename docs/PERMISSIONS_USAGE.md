# Role-Based Permission System - Usage Guide

## Overview
This system provides a flexible, role-based permission mechanism for Django REST Framework views.

## Components

### 1. Models

#### Permission
Represents a single permission in the system.
```python
from apps.core.models import Permission

# Create a permission
permission = Permission.objects.create(
    code="document.create",
    description="Tạo tài liệu"
)
```

#### Role
Groups multiple permissions together.
```python
from apps.core.models import Role, Permission

# Create a role
role = Role.objects.create(
    name="Editor",
    description="Người biên tập"
)

# Add permissions to role
permission1 = Permission.objects.get(code="document.create")
permission2 = Permission.objects.get(code="document.edit")
role.permissions.add(permission1, permission2)
```

#### User
Users can have multiple roles.
```python
from apps.core.models import User

user = User.objects.get(username="john")
role = Role.objects.get(name="Editor")

# Assign role to user
user.role = role
user.save()

# Check if user has permission
if user.has_permission("document.create"):
    # User can create documents
    pass
```

### 2. Decorator: @register_permission

Use this decorator to mark views that require specific permissions.

#### Function-Based Views
```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils import register_permission

@api_view(["POST"])
@permission_classes([RoleBasedPermission])
@register_permission("document.create", "Tạo tài liệu")
def document_create(request):
    # Your view logic here
    return Response({"message": "Document created"})
```

#### Class-Based Views
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils import register_permission

class DocumentView(APIView):
    permission_classes = [RoleBasedPermission]
    
    @register_permission("document.list", "Xem danh sách tài liệu")
    def get(self, request):
        # List documents
        return Response({"documents": []})
    
    @register_permission("document.create", "Tạo tài liệu")
    def post(self, request):
        # Create document
        return Response({"message": "Document created"})
```

#### ViewSets
```python
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils import register_permission

class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [RoleBasedPermission]
    
    @register_permission("document.list", "Xem danh sách tài liệu")
    def list(self, request):
        return Response({"documents": []})
    
    @register_permission("document.create", "Tạo tài liệu")
    def create(self, request):
        return Response({"message": "Document created"})
    
    @action(detail=True, methods=["post"])
    @register_permission("document.approve", "Phê duyệt tài liệu")
    def approve(self, request, pk=None):
        return Response({"message": "Document approved"})
```

### 3. Permission Class: RoleBasedPermission

This is the DRF permission class that checks if users have the required permissions.

**Features:**
- Automatically extracts permission code from the decorator
- Checks if the user is authenticated
- Allows all requests from superusers
- Checks if user has permission through their roles
- Returns clear error messages

**Behavior:**
- Views without `@register_permission` decorator are accessible to all authenticated users
- Views with decorator require the user to have the specific permission
- Superusers bypass all permission checks
- Unauthenticated users are denied with "Bạn cần đăng nhập để thực hiện hành động này"
- Users without permission are denied with "Bạn không có quyền thực hiện hành động này"

### 4. Management Command: collect_permissions

Scans all URL patterns in your Django project and syncs permissions to the database.

#### Usage
```bash
python manage.py collect_permissions
```

#### What it does:
1. Scans all URL patterns (including nested URLconfs)
2. Finds all views decorated with `@register_permission`
3. Creates new permissions in the database
4. Updates descriptions of existing permissions
5. Does NOT delete permissions that are no longer in code

#### Output Example
```
Collecting permissions from views...
Successfully collected 15 permissions (5 created, 10 updated)
```

## Complete Workflow

### 1. Developer defines views with permissions
```python
@api_view(["POST"])
@permission_classes([RoleBasedPermission])
@register_permission("document.create", "Tạo tài liệu")
def document_create(request):
    return Response({"message": "Created"})
```

### 2. Admin collects permissions
```bash
python manage.py collect_permissions
```

### 3. Admin creates roles and assigns permissions
```python
# In Django admin or management command
editor_role = Role.objects.create(name="Editor")
create_perm = Permission.objects.get(code="document.create")
editor_role.permissions.add(create_perm)
```

### 4. Admin assigns roles to users
```python
user = User.objects.get(username="john")
editor_role = Role.objects.get(name="Editor")
user.role = editor_role
user.save()
```

### 5. User makes API request
When the user calls the API:
- `RoleBasedPermission` checks if they have the required permission
- If yes, the view executes
- If no, they get a 403 Forbidden response

## Best Practices

1. **Use descriptive permission codes**: Follow the pattern `{resource}.{action}`, e.g., "document.create", "user.delete"

2. **Write clear descriptions**: Use Vietnamese descriptions that clearly explain what the permission allows

3. **Run collect_permissions after code changes**: Always run the command after adding or modifying permission decorators

4. **Don't delete permissions manually**: The command doesn't delete old permissions, so you need to clean them up manually if needed

5. **Use consistent naming**: Keep permission codes consistent across your application

6. **Group related permissions**: Create roles that logically group related permissions

## Error Messages

- **401 Unauthorized**: User is not authenticated
- **403 Forbidden - "Bạn cần đăng nhập để thực hiện hành động này"**: User is not logged in
- **403 Forbidden - "Bạn không có quyền thực hiện hành động này"**: User is logged in but doesn't have the required permission

## Testing

Always test your permissions:
```python
from django.test import TestCase
from apps.core.models import User, Role, Permission

class MyViewPermissionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass"
        )
        self.permission = Permission.objects.create(
            code="document.create",
            description="Tạo tài liệu"
        )
        self.role = Role.objects.create(name="Editor")
        self.role.permissions.add(self.permission)
    
    def test_user_with_permission_can_access(self):
        self.user.role = self.role
        self.user.save()
        # Test your view here
        
    def test_user_without_permission_cannot_access(self):
        # User has no roles
        # Test that view returns 403
```
