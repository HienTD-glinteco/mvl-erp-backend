# Migration Guide: Converting ViewSets to Use Auto Permission Registration

This guide provides step-by-step instructions for migrating existing ViewSets to use the new automatic permission registration system via `BaseModelViewSet` and `BaseReadOnlyModelViewSet`.

## Prerequisites

Before migrating, ensure you understand:
- The [Auto Permission Registration documentation](AUTO_PERMISSION_REGISTRATION.md)
- Your ViewSet's current permission structure
- The module/submodule organization of your app

## Migration Steps

### Step 1: Identify ViewSets to Migrate

Find all ViewSets in your app that currently inherit from:
- `viewsets.ModelViewSet`
- `viewsets.ReadOnlyModelViewSet`
- Or use `@register_permission` decorators on actions

### Step 2: Update Imports

**Before:**
```python
from rest_framework import viewsets
```

**After:**
```python
from libs import BaseModelViewSet, BaseReadOnlyModelViewSet
```

### Step 3: Change Base Class

**For Full CRUD ViewSets:**
```python
# Before
class MyViewSet(AuditLoggingMixin, viewsets.ModelViewSet):
    pass

# After
class MyViewSet(AuditLoggingMixin, BaseModelViewSet):
    pass
```

**For Read-Only ViewSets:**
```python
# Before
class MyViewSet(viewsets.ReadOnlyModelViewSet):
    pass

# After
class MyViewSet(BaseReadOnlyModelViewSet):
    pass
```

### Step 4: Add Permission Attributes

Add three class attributes to your ViewSet:

```python
class MyViewSet(BaseModelViewSet):
    # ... existing attributes ...
    
    # Permission registration attributes
    module = "YourModule"           # e.g., "HRM", "Core", "CRM"
    submodule = "YourSubmodule"     # e.g., "Employee Management", "Document Management"
    permission_prefix = "prefix"     # e.g., "employee", "document", "role"
```

### Step 5: Remove Old Decorators (Optional)

If you were using `@register_permission` decorators, you can now remove them:

**Before:**
```python
from apps.core.utils import register_permission

class MyViewSet(viewsets.ModelViewSet):
    @register_permission("mymodel.list", "List items", module="MyModule")
    def list(self, request):
        return super().list(request)
    
    @register_permission("mymodel.create", "Create item", module="MyModule")
    def create(self, request):
        return super().create(request)
```

**After:**
```python
from libs import BaseModelViewSet

class MyViewSet(BaseModelViewSet):
    module = "MyModule"
    submodule = "Item Management"
    permission_prefix = "mymodel"
    
    # No decorators needed - permissions are auto-generated!
```

### Step 6: Run Collect Permissions

After migration, run the management command to sync permissions to the database:

```bash
python manage.py collect_permissions
```

### Step 7: Verify Permissions

Check that permissions were created correctly:

```python
from apps.core.models import Permission

# List all permissions for your prefix
perms = Permission.objects.filter(code__startswith="mymodel.")
for perm in perms:
    print(f"{perm.code}: {perm.name} ({perm.module} > {perm.submodule})")
```

## Migration Examples

### Example 1: BranchViewSet (HRM Module)

**Before:**
```python
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging import AuditLoggingMixin
from apps.hrm.api.serializers import BranchSerializer
from apps.hrm.models import Branch

@extend_schema_view(
    list=extend_schema(
        summary="List all branches",
        description="Retrieve a list of all branches in the system",
        tags=["Branch"],
    ),
    # ... other schema decorators ...
)
class BranchViewSet(AuditLoggingMixin, viewsets.ModelViewSet):
    """ViewSet for Branch model"""
    
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["code"]
```

**After:**
```python
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging import AuditLoggingMixin
from apps.hrm.api.serializers import BranchSerializer
from apps.hrm.models import Branch
from libs import BaseModelViewSet

@extend_schema_view(
    list=extend_schema(
        summary="List all branches",
        description="Retrieve a list of all branches in the system",
        tags=["Branch"],
    ),
    # ... other schema decorators ...
)
class BranchViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Branch model"""
    
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["code"]
    
    # Permission registration attributes
    module = "HRM"
    submodule = "Organization"
    permission_prefix = "branch"
```

**Generated Permissions:**
- `branch.list` - List Branches
- `branch.retrieve` - View Branch
- `branch.create` - Create Branch
- `branch.update` - Update Branch
- `branch.partial_update` - Partially Update Branch
- `branch.destroy` - Delete Branch

### Example 2: NotificationViewSet (Notifications Module)

**Before:**
```python
from rest_framework import viewsets
from apps.notifications.models import Notification
from apps.notifications.api.serializers import NotificationSerializer

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Notification model - Read only"""
    
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
```

**After:**
```python
from apps.notifications.models import Notification
from apps.notifications.api.serializers import NotificationSerializer
from libs import BaseReadOnlyModelViewSet

class NotificationViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Notification model - Read only"""
    
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    
    # Permission registration attributes
    module = "Notifications"
    submodule = "User Notifications"
    permission_prefix = "notification"
```

**Generated Permissions:**
- `notification.list` - List Notifications
- `notification.retrieve` - View Notification

### Example 3: DepartmentViewSet with Custom Actions

**Before:**
```python
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.hrm.models import Department
from apps.hrm.api.serializers import DepartmentSerializer

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    
    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Get department tree structure"""
        # Implementation here
        return Response(tree_data)
    
    @action(detail=False, methods=["get"])
    def function_choices(self, request):
        """Get function choices based on block type"""
        # Implementation here
        return Response(choices)
```

**After:**
```python
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.hrm.models import Department
from apps.hrm.api.serializers import DepartmentSerializer
from libs import BaseModelViewSet

class DepartmentViewSet(BaseModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    
    # Permission registration attributes
    module = "HRM"
    submodule = "Organization"
    permission_prefix = "department"
    
    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Get department tree structure"""
        # Implementation here
        return Response(tree_data)
    
    @action(detail=False, methods=["get"])
    def function_choices(self, request):
        """Get function choices based on block type"""
        # Implementation here
        return Response(choices)
```

**Generated Permissions:**
- `department.list` - List Departments
- `department.retrieve` - View Department
- `department.create` - Create Department
- `department.update` - Update Department
- `department.partial_update` - Partially Update Department
- `department.destroy` - Delete Department
- `department.tree` - Tree Department (custom action)
- `department.function_choices` - Function Choices Department (custom action)

## Common Issues and Solutions

### Issue 1: Permission Codes Already Exist

**Problem:** You already have permissions with the same codes in the database.

**Solution:** The `collect_permissions` command uses `update_or_create`, so existing permissions will be updated with the new metadata. No manual intervention needed.

### Issue 2: Choosing the Right permission_prefix

**Problem:** Not sure what to use as the permission prefix.

**Solution:** Use the lowercase, singular form of your model name. Examples:
- Model: `Branch` → Prefix: `branch`
- Model: `Employee` → Prefix: `employee`
- Model: `OrganizationChart` → Prefix: `organization_chart`

### Issue 3: ViewSet with Mixed Inheritance

**Problem:** ViewSet inherits from multiple mixins and ViewSet classes.

**Solution:** Replace only the ViewSet base class:

```python
# Before
class MyViewSet(CustomMixin, AuditLoggingMixin, viewsets.ModelViewSet):
    pass

# After
class MyViewSet(CustomMixin, AuditLoggingMixin, BaseModelViewSet):
    pass
```

The order matters - keep your custom mixins first, then BaseModelViewSet last.

### Issue 4: Custom Permission Names

**Problem:** Need custom permission names that don't follow the auto-generated pattern.

**Solution:** Override `get_registered_permissions()`:

```python
class MyViewSet(BaseModelViewSet):
    module = "MyModule"
    submodule = "My Submodule"
    permission_prefix = "mymodel"
    
    @classmethod
    def get_registered_permissions(cls):
        permissions = super().get_registered_permissions()
        
        # Customize specific permission
        for perm in permissions:
            if perm["code"] == "mymodel.list":
                perm["name"] = "View All My Items"
        
        return permissions
```

## Checklist for Each ViewSet

Use this checklist when migrating a ViewSet:

- [ ] Update imports to include `BaseModelViewSet` or `BaseReadOnlyModelViewSet`
- [ ] Change base class from `viewsets.ModelViewSet` to `BaseModelViewSet` (or ReadOnly variant)
- [ ] Add `module` attribute
- [ ] Add `submodule` attribute
- [ ] Add `permission_prefix` attribute
- [ ] Remove `@register_permission` decorators (if any)
- [ ] Run `python manage.py collect_permissions`
- [ ] Verify permissions in database
- [ ] Update tests (if they check for specific permission codes)
- [ ] Commit changes

## Migration Schedule

Recommended approach for large projects:

1. **Phase 1**: Migrate core ViewSets (Role, Permission, etc.)
2. **Phase 2**: Migrate high-traffic ViewSets
3. **Phase 3**: Migrate remaining ViewSets
4. **Phase 4**: Remove old decorator-based permissions from codebase

You can migrate gradually - both systems work together during the transition period.

## Testing After Migration

### Manual Testing

1. Run collect_permissions:
   ```bash
   python manage.py collect_permissions
   ```

2. Check the output for your ViewSet

3. Query the database:
   ```python
   from apps.core.models import Permission
   Permission.objects.filter(code__startswith="yourprefix.")
   ```

### Automated Testing

Add tests to verify permission generation:

```python
def test_my_viewset_generates_permissions(self):
    from apps.myapp.api.views import MyViewSet
    
    permissions = MyViewSet.get_registered_permissions()
    
    codes = [p["code"] for p in permissions]
    assert "mymodel.list" in codes
    assert "mymodel.create" in codes
    
    list_perm = next(p for p in permissions if p["code"] == "mymodel.list")
    assert list_perm["module"] == "MyModule"
    assert list_perm["submodule"] == "My Submodule"
```

## Rollback Plan

If you need to rollback:

1. Restore the old ViewSet code from git
2. The permissions in the database remain unchanged
3. The old decorator-based system will work as before

## Questions?

See the [FAQ section in the main documentation](AUTO_PERMISSION_REGISTRATION.md#faq) or reach out to the development team.
