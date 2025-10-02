# Role API Documentation

This document describes the Role Management API endpoints for the backend system.

## Overview

The Role API allows management of user roles (Vai trò) in the system, including:
- System-defined roles (VT001, VT002)
- Custom user-created roles (VT003+)
- Permission assignment to roles
- Role assignment to users

## Base URL

All role endpoints are under: `/api/core/roles/`

## Authentication

All endpoints require authentication using JWT tokens.

## Endpoints

### 1. List Roles

**GET** `/api/core/roles/`

Get list of all roles in the system.

**Query Parameters:**
- `search` (string): Search by name, code, or description
- `name` (string): Filter by name (case-insensitive contains)
- `code` (string): Filter by code (case-insensitive contains)
- `is_system_role` (boolean): Filter by system role status
- `ordering` (string): Order by field (e.g., `code`, `-name`, `created_at`)
- `page` (integer): Page number for pagination
- `page_size` (integer): Number of items per page

**Example Request:**
```bash
GET /api/core/roles/?search=Admin&ordering=code
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "code": "VT001",
      "name": "Admin hệ thống",
      "description": "Vai trò có tất cả các quyền của hệ thống",
      "is_system_role": true,
      "created_by": "Hệ thống",
      "permissions_detail": [
        {
          "id": 1,
          "name": "Can add user",
          "codename": "add_user",
          "content_type": 4
        }
      ],
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

### 2. Create Role

**POST** `/api/core/roles/`

Create a new role in the system.

**Request Body:**
```json
{
  "name": "Quản trị viên chi nhánh",
  "description": "Vai trò quản lý chi nhánh",
  "permission_ids": [1, 2, 3, 5, 8]
}
```

**Field Descriptions:**
- `name` (string, required): Role name (must be unique)
- `description` (string, optional): Role description
- `permission_ids` (array, required): List of permission IDs (at least 1 required)

**Business Rules:**
- Role code is auto-generated in format VTxxx (starting from VT003)
- At least one permission must be selected
- Role name must be unique
- `is_system_role` is automatically set to `false` for user-created roles

**Success Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": 3,
    "code": "VT003",
    "name": "Quản trị viên chi nhánh",
    "description": "Vai trò quản lý chi nhánh",
    "is_system_role": false,
    "created_by": "Người dùng",
    "permissions_detail": [...],
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  }
}
```

**Error Responses:**

- **400 Bad Request** - No permissions selected:
```json
{
  "success": false,
  "errors": {
    "permission_ids": ["Cần chọn ít nhất 1 Quyền"]
  }
}
```

- **400 Bad Request** - Duplicate name:
```json
{
  "success": false,
  "errors": {
    "name": ["Tên vai trò đã tồn tại."]
  }
}
```

### 3. Retrieve Role

**GET** `/api/core/roles/{id}/`

Get detailed information about a specific role.

**Path Parameters:**
- `id` (integer): Role ID

**Example Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "code": "VT001",
    "name": "Admin hệ thống",
    "description": "Vai trò có tất cả các quyền của hệ thống",
    "is_system_role": true,
    "created_by": "Hệ thống",
    "permissions_detail": [
      {
        "id": 1,
        "name": "Can add user",
        "codename": "add_user",
        "content_type": 4
      }
    ],
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  }
}
```

### 4. Update Role

**PATCH** `/api/core/roles/{id}/`

Update role information.

**Path Parameters:**
- `id` (integer): Role ID

**Request Body:**
```json
{
  "name": "Updated Role Name",
  "description": "Updated description",
  "permission_ids": [1, 2, 3]
}
```

**Business Rules:**
- Cannot update system roles (VT001, VT002)
- Role code cannot be changed
- Name must remain unique
- Can update name, description, and permissions

**Success Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": 3,
    "code": "VT003",
    "name": "Updated Role Name",
    "description": "Updated description",
    "is_system_role": false,
    "created_by": "Người dùng",
    "permissions_detail": [...],
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T14:20:00Z"
  }
}
```

**Error Responses:**

- **400 Bad Request** - Attempting to update system role:
```json
{
  "success": false,
  "errors": ["Không thể chỉnh sửa vai trò hệ thống."]
}
```

### 5. Delete Role

**DELETE** `/api/core/roles/{id}/`

Delete a role from the system.

**Path Parameters:**
- `id` (integer): Role ID

**Business Rules:**
- Cannot delete system roles (VT001, VT002)
- Cannot delete roles that are currently assigned to users
- Confirmation required before deletion

**Success Response (204 No Content):**
```
HTTP 204 No Content
```

**Error Responses:**

- **400 Bad Request** - System role:
```json
{
  "success": false,
  "detail": "Không thể xóa vai trò hệ thống."
}
```

- **400 Bad Request** - Role in use:
```json
{
  "success": false,
  "detail": "Vai trò đang được sử dụng bởi nhân viên."
}
```

## System Roles

The system automatically creates two predefined roles:

### VT001 - Admin hệ thống
- **Code**: VT001
- **Name**: Admin hệ thống
- **Description**: Vai trò có tất cả các quyền của hệ thống
- **Permissions**: All system permissions
- **Features**:
  - Cannot be edited
  - Cannot be deleted
  - Has full system access

### VT002 - Vai trò cơ bản
- **Code**: VT002
- **Name**: Vai trò cơ bản
- **Description**: Vai trò mặc định của tài khoản nhân viên khi được tạo mới
- **Permissions**: Basic permissions (to be defined)
- **Features**:
  - Cannot be edited
  - Cannot be deleted
  - Default role for new employees

## Search Functionality

The search functionality follows these rules:

1. **Case-insensitive**: Search is not case-sensitive
2. **Continuous substring**: Search term must be a continuous substring
3. **Examples**:
   - Role name: "Quản trị viên"
   - Search "Quản trị" → Found ✓
   - Search "Quản viên" → Not found ✗ (not continuous)

**Example Search Request:**
```bash
GET /api/core/roles/?search=Quản trị
```

## Filtering

### Filter by Name (Case-insensitive)
```bash
GET /api/core/roles/?name=admin
```

### Filter by System Role Status
```bash
# Only system roles
GET /api/core/roles/?is_system_role=true

# Only user-created roles
GET /api/core/roles/?is_system_role=false
```

### Combined Filters
```bash
GET /api/core/roles/?is_system_role=false&ordering=name
```

## Ordering

Available ordering fields:
- `code` - Order by role code
- `name` - Order by role name
- `created_at` - Order by creation date
- Use `-` prefix for descending order (e.g., `-name`)

**Examples:**
```bash
# Ascending by code (default)
GET /api/core/roles/?ordering=code

# Descending by name
GET /api/core/roles/?ordering=-name

# By creation date
GET /api/core/roles/?ordering=created_at
```

## Error Handling

All endpoints follow standard error response format:

```json
{
  "success": false,
  "errors": {
    "field_name": ["Error message"]
  }
}
```

## Permissions

To access these endpoints, users must have appropriate permissions:
- `view_role` - View role list and details
- `add_role` - Create new roles
- `change_role` - Update existing roles
- `delete_role` - Delete roles

## Notes

1. **Created By Field**: The `created_by` field displays:
   - "Hệ thống" for system roles (VT001, VT002)
   - "Người dùng" for user-created roles

2. **Code Generation**: Role codes are automatically generated sequentially starting from VT003

3. **User Assignment**: When a role is assigned to users, it appears in the User model's `role` field

4. **Permission Management**: Permissions are managed through Django's built-in permission system

5. **Validation**: All required fields must be provided, and business rules are enforced at the API level
