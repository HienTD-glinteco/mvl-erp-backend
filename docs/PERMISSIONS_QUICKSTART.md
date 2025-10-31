# Permission System - Quick Start Guide

## 🚀 5-Minute Quick Start

### 1. Define a Protected View

```python
# apps/myapp/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils import register_permission

@api_view(["POST"])
@permission_classes([RoleBasedPermission])
@register_permission("document.create", "Tạo tài liệu")
def create_document(request):
    return Response({"message": "Document created"})
```

### 2. Collect Permissions

```bash
python manage.py collect_permissions
```

### 3. Setup Roles (Django Shell)

```python
from apps.core.models import Permission, Role, User

# Get the permission
perm = Permission.objects.get(code="document.create")

# Create a role
role = Role.objects.create(name="Editor")
role.permissions.add(perm)

# Assign role to user
user = User.objects.get(username="john")
user.role = role
user.save()
```

### 4. Test

```bash
# The user can now call the create_document API
curl -X POST http://localhost:8000/api/document/create/ \
  -H "Authorization: Bearer <token>"
```

---

## 📋 Decorator Patterns

### Function-Based View
```python
@api_view(["GET"])
@permission_classes([RoleBasedPermission])
@register_permission("resource.action", "Mô tả")
def my_view(request):
    pass
```

### Class-Based View
```python
class MyView(APIView):
    permission_classes = [RoleBasedPermission]

    @register_permission("resource.list", "Xem danh sách")
    def get(self, request):
        pass

    @register_permission("resource.create", "Tạo mới")
    def post(self, request):
        pass
```

### ViewSet
```python
class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [RoleBasedPermission]

    @register_permission("resource.list", "Xem danh sách")
    def list(self, request):
        pass

    @action(detail=True, methods=["post"])
    @register_permission("resource.approve", "Phê duyệt")
    def approve(self, request, pk=None):
        pass
```

---

## 🎯 Permission Code Naming

| Pattern | Example | Description |
|---------|---------|-------------|
| `{resource}.{action}` | `document.create` | ✅ Recommended |
| `{app}.{resource}.{action}` | `hrm.employee.create` | ✅ For complex apps |
| `{resource}-{action}` | `document-create` | ❌ Avoid |
| `{action}_{resource}` | `create_document` | ❌ Avoid |

---

## 🔑 Common Commands

```bash
# Collect all permissions from code
python manage.py collect_permissions

# Run permission tests
python manage.py test apps.core.tests.test_permissions

# Run demo
python manage.py shell < docs/PERMISSIONS_DEMO.py

# Check a user's permissions (Django shell)
python manage.py shell
>>> from apps.core.models import User
>>> user = User.objects.get(username="john")
>>> user.has_permission("document.create")
True
```

---

## 🛠️ Django Admin Setup

1. Register models in admin:

```python
# apps/core/admin.py
from django.contrib import admin
from apps.core.models import Permission, Role

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["code", "description", "created_at"]
    search_fields = ["code", "description"]

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "created_at"]
    filter_horizontal = ["permissions"]
    search_fields = ["name", "description"]

# Add roles to UserAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.core.models import User

class UserAdmin(BaseUserAdmin):
    filter_horizontal = BaseUserAdmin.filter_horizontal + ("roles",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Roles & Permissions", {"fields": ("roles",)}),
    )

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
```

---

## 🔍 Debugging Checklist

Permission denied? Check:

- [ ] Is `@register_permission` decorator present?
- [ ] Is `RoleBasedPermission` in `permission_classes`?
- [ ] Did you run `collect_permissions`?
- [ ] Does the permission exist in database?
- [ ] Does the role have the permission?
- [ ] Is the role assigned to the user?
- [ ] Is the user authenticated?

Quick debug:

```python
# Django shell
from apps.core.models import User
user = User.objects.get(username="john")

# Check user's roles
print(user.roles.all())

# Check permissions per role
for role in user.roles.all():
    print(f"{role.name}: {list(role.permissions.values_list('code', flat=True))}")

# Check specific permission
print(user.has_permission("document.create"))
```

---

## 📚 Further Reading

- **Full Documentation**: [PERMISSIONS_SYSTEM.md](./PERMISSIONS_SYSTEM.md)
- **Usage Examples**: [PERMISSIONS_USAGE.md](./PERMISSIONS_USAGE.md)
- **Demo Script**: [PERMISSIONS_DEMO.py](./PERMISSIONS_DEMO.py)

---

## 💡 Pro Tips

1. **Run collect_permissions in CI/CD**: Add it to your deployment pipeline
2. **Superusers bypass all checks**: Use roles for regular admins
3. **Views without decorator are accessible**: Only add decorator when needed
4. **Permission codes are case-sensitive**: Use lowercase consistently
5. **One permission per endpoint**: Don't reuse permission codes across different actions

---

## 🐛 Common Mistakes

❌ **Wrong**: Decorator below permission_classes
```python
@permission_classes([RoleBasedPermission])
@register_permission("document.create", "Tạo")  # Wrong order!
def my_view(request):
    pass
```

✅ **Correct**: Decorator above permission_classes
```python
@register_permission("document.create", "Tạo")
@permission_classes([RoleBasedPermission])
def my_view(request):
    pass
```

---

❌ **Wrong**: English description
```python
@register_permission("document.create", "Create document")  # Wrong!
```

✅ **Correct**: Vietnamese description
```python
@register_permission("document.create", "Tạo tài liệu")  # Correct!
```

---

❌ **Wrong**: Missing permission class
```python
@register_permission("document.create", "Tạo")  # Decorator alone doesn't work!
def my_view(request):
    pass
```

✅ **Correct**: Both decorator and permission class
```python
@permission_classes([RoleBasedPermission])
@register_permission("document.create", "Tạo")
def my_view(request):
    pass
```
