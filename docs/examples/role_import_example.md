# Example: Adding Import to Role ViewSet

This example demonstrates how to add XLSX import functionality to an existing ViewSet.

## Current Implementation

The `RoleViewSet` currently looks like this:

```python
from apps.audit_logging import AuditLoggingMixin
from apps.core.api.filtersets import RoleFilterSet
from apps.core.api.serializers import RoleSerializer
from apps.core.models import Role
from libs import BaseModelViewSet


class RoleViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Role model"""

    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    module = "Core"
    submodule = "Role Management"
    permission_prefix = "role"
```

## Adding Import Functionality

To add import functionality, simply add `ImportXLSXMixin` to the class inheritance:

```python
from apps.audit_logging import AuditLoggingMixin
from apps.core.api.filtersets import RoleFilterSet
from apps.core.api.serializers import RoleSerializer
from apps.core.models import Role
from libs import BaseModelViewSet, ImportXLSXMixin  # Add ImportXLSXMixin


class RoleViewSet(AuditLoggingMixin, ImportXLSXMixin, BaseModelViewSet):
    """ViewSet for Role model with import functionality"""

    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    module = "Core"
    submodule = "Role Management"
    permission_prefix = "role"
```

**That's it!** The ViewSet now has an `/import/` endpoint.

## What's Automatically Enabled

### 1. Auto Schema Generation

The mixin automatically generates an import schema from the Role model:

```python
{
    "fields": ["code", "name", "description", "is_system_role"],
    "required": ["code", "name"]
}
```

**Excluded fields:**
- `id` (AutoField)
- `created_at`, `updated_at` (timestamp fields)
- `permissions` (ManyToMany field - not supported in basic import)

### 2. Import Endpoint

**POST** `/api/roles/import/`

**Excel Format:**
```
| code  | name          | description                | is_system_role |
|-------|---------------|----------------------------|----------------|
| ADMIN | Administrator | Full system access         | false          |
| USER  | Regular User  | Standard user permissions  | false          |
```

### 3. Validation

Each row is validated using `RoleSerializer`:
- `code`: Required, unique, max 50 characters
- `name`: Required, unique, max 100 characters
- `description`: Optional, max 255 characters
- `is_system_role`: Optional boolean, defaults to false

### 4. Error Reporting

If there are errors, the response includes details:

```json
{
  "success_count": 1,
  "error_count": 1,
  "errors": [
    {
      "row": 3,
      "errors": {
        "code": ["Role with this Role code already exists."]
      }
    }
  ],
  "detail": "Import completed successfully"
}
```

### 5. Audit Logging

Because `AuditLoggingMixin` is included, each imported role is automatically logged with:
- Action: `IMPORT`
- User: Current authenticated user
- Request metadata: IP address, user agent
- Object details: Role code and name

### 6. Permission Generation

The import action automatically generates a new permission:

```python
{
    "code": "role.import_data",
    "name": "Import Data Roles",
    "description": "Import Data a Role",
    "module": "Core",
    "submodule": "Role Management"
}
```

Run `poetry run python manage.py collect_permissions` to sync to database.

## Customizing Import (Optional)

If you need to customize the import schema, override `get_import_schema`:

```python
class RoleViewSet(AuditLoggingMixin, ImportXLSXMixin, BaseModelViewSet):
    # ... existing code ...

    def get_import_schema(self, request, file):
        """
        Custom import schema.
        
        Excludes is_system_role from import to prevent 
        users from creating system roles via import.
        """
        return {
            "fields": ["code", "name", "description"],
            "required": ["code", "name"]
        }
```

## Testing Import

### Create Test XLSX File

```python
import io
from openpyxl import Workbook


def create_role_import_file():
    """Create test XLSX file for role import"""
    workbook = Workbook()
    sheet = workbook.active
    
    # Headers
    sheet["A1"] = "code"
    sheet["B1"] = "name"
    sheet["C1"] = "description"
    
    # Data
    sheet["A2"] = "ADMIN"
    sheet["B2"] = "Administrator"
    sheet["C2"] = "Full system access"
    
    sheet["A3"] = "USER"
    sheet["B3"] = "Regular User"
    sheet["C3"] = "Standard user permissions"
    
    # Save to bytes
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    output.name = "roles.xlsx"
    return output
```

### Test Import

```python
from rest_framework.test import APIClient


def test_import_roles():
    """Test role import functionality"""
    client = APIClient()
    client.login(username="admin", password="password")
    
    # Create test file
    file = create_role_import_file()
    
    # Import
    response = client.post("/api/roles/import/", {"file": file}, format="multipart")
    
    # Validate
    assert response.status_code == 200
    assert response.data["success_count"] == 2
    assert response.data["error_count"] == 0
    
    # Check database
    assert Role.objects.filter(code="ADMIN").exists()
    assert Role.objects.filter(code="USER").exists()
```

## API Documentation

The import endpoint is automatically documented in the OpenAPI schema:

**Swagger UI:** `/api/schema/swagger-ui/`

**Endpoint:** `POST /api/roles/import/`

**Request Body:**
- Content-Type: `multipart/form-data`
- Parameter: `file` (binary, required)

**Responses:**
- 200: Success with import summary
- 400: Bad request (no file, invalid file type, validation errors)
- 500: Server error

## Frontend Integration Example

### JavaScript/Fetch

```javascript
async function importRoles(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/roles/import/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
    },
    body: formData,
  });

  const result = await response.json();
  
  if (result.error_count > 0) {
    console.warn('Import completed with errors:', result.errors);
  } else {
    console.log(`Successfully imported ${result.success_count} roles`);
  }
  
  return result;
}
```

### React Example

```jsx
import React, { useState } from 'react';

function RoleImporter() {
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setImporting(true);
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/roles/import/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      });

      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Import failed:', error);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div>
      <h2>Import Roles</h2>
      <input 
        type="file" 
        accept=".xlsx"
        onChange={handleFileUpload}
        disabled={importing}
      />
      
      {importing && <p>Importing...</p>}
      
      {result && (
        <div>
          <p>Success: {result.success_count} roles imported</p>
          {result.error_count > 0 && (
            <div>
              <p>Errors: {result.error_count}</p>
              <ul>
                {result.errors.map((error, idx) => (
                  <li key={idx}>
                    Row {error.row}: {JSON.stringify(error.errors)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

## Migration Guide

If you have existing role data in Excel and want to import it:

1. **Prepare Excel file** with columns: `code`, `name`, `description`
2. **Ensure unique codes** - each role must have a unique code
3. **Validate data** - check that all required fields are filled
4. **Test import** with a small sample first
5. **Run full import** once validated
6. **Verify results** - check error report and database

## Summary

Adding import functionality to any ViewSet is as simple as:

1. Add `ImportXLSXMixin` to class inheritance
2. Ensure proper mixin order (AuditLoggingMixin first if used)
3. Optionally customize schema with `get_import_schema()`
4. Run `collect_permissions` to sync new permission

The mixin handles everything else:
- ✅ Schema generation
- ✅ Excel parsing
- ✅ Validation
- ✅ Error reporting
- ✅ Bulk import
- ✅ Audit logging
- ✅ Permission registration
- ✅ API documentation
