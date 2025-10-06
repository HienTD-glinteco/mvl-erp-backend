# Employee Role Management API Documentation

## Overview

The Employee Role Management API allows viewing and managing employees based on their assigned roles within the organizational structure. This API provides:

- Listing employees with role and organizational information
- Searching and filtering employees by various criteria
- Bulk updating employee roles (maximum 25 employees at once)
- Automatic session invalidation when roles change

## Base URL

All endpoints are under: `/api/hrm/employee-roles/`

## Authentication

All endpoints require authentication using JWT tokens.

## Endpoints

### 1. List Employees by Role

**GET** `/api/hrm/employee-roles/`

Get a list of employees with their role and organizational information.

**Query Parameters:**

- `search` (string, optional): Search by employee name or role name (case-insensitive)
- `branch` (integer, optional): Filter by branch ID
- `block` (integer, optional): Filter by block ID
- `department` (integer, optional): Filter by department ID
- `position` (integer, optional): Filter by position ID
- `role` (integer, optional): Filter by role ID
- `ordering` (string, optional): Sort by field. Default: `-username` (descending by employee code)
  - Available fields: `username`, `first_name`, `last_name`, `role__name`, `created_at`
  - Add `-` prefix for descending order (e.g., `-username`)
- `page` (integer, optional): Page number for pagination
- `page_size` (integer, optional): Number of results per page

**Business Rules:**

- QTNV 3.2.1.1: Default sorting is descending by employee code (username)
- QTNV 3.2.1.2: Search matches continuous substrings in employee name or role name (case-insensitive)
- QTNV 3.2.1.3: Filters can be combined
  - `Chi nhánh`, `Chức vụ`, `Vai trò` are independent
  - `Khối` filter only works when `Chi nhánh` is selected
  - `Phòng ban` filter only works when `Khối` is selected

**Success Response (200 OK):**

```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "employee_code": "NV001",
      "employee_name": "Nguyễn Văn A",
      "branch_name": "Chi nhánh Hà Nội",
      "block_name": "Khối Kinh doanh",
      "department_name": "Phòng Kinh doanh 1",
      "position_name": "Nhân viên Kinh doanh",
      "role": 3,
      "role_name": "Staff"
    },
    {
      "id": 124,
      "employee_code": "NV002",
      "employee_name": "Trần Thị B",
      "branch_name": "Chi nhánh Hà Nội",
      "block_name": "Khối Kinh doanh",
      "department_name": "Phòng Kinh doanh 1",
      "position_name": "Nhân viên Kinh doanh",
      "role": 2,
      "role_name": "Manager"
    }
  ],
  "error": null
}
```

**Example Requests:**

```bash
# List all employees (default: descending by employee code)
GET /api/hrm/employee-roles/

# Search by employee name
GET /api/hrm/employee-roles/?search=Nguyễn

# Search by role name
GET /api/hrm/employee-roles/?search=Manager

# Filter by branch
GET /api/hrm/employee-roles/?branch=1

# Filter by role
GET /api/hrm/employee-roles/?role=3

# Combine search and filters
GET /api/hrm/employee-roles/?search=Văn&role=3

# Custom sorting (ascending by name)
GET /api/hrm/employee-roles/?ordering=first_name
```

---

### 2. Bulk Update Employee Roles

**POST** `/api/hrm/employee-roles/bulk-update-roles/`

Update roles for multiple employees at once.

**Request Body:**

```json
{
  "employee_ids": [123, 124, 125],
  "new_role_id": 5
}
```

**Parameters:**

- `employee_ids` (array of integers, required): List of employee IDs to update
  - Minimum: 1 employee
  - Maximum: 25 employees
- `new_role_id` (integer, required): ID of the new role to assign

**Business Rules:**

- QTNV 3.2.4: Maximum 25 employees can be updated at once
- QTNV 3.2.4: At least one employee must be selected
- QTNV 3.2.4: New role must be selected
- QTNV 3.2.4: When role is updated, all active sessions for affected users are invalidated (force logout)
- Only employees whose role actually changes are counted in `updated_count`

**Success Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "Chỉnh sửa thành công",
    "updated_count": 3
  },
  "error": null
}
```

**Error Responses:**

- **400 Bad Request** - No employees selected:

```json
{
  "success": false,
  "data": null,
  "error": {
    "type": "validation_error",
    "errors": [
      {
        "code": "invalid",
        "detail": "Please select at least one employee.",
        "attr": "employee_ids"
      }
    ]
  }
}
```

- **400 Bad Request** - Too many employees:

```json
{
  "success": false,
  "data": null,
  "error": {
    "type": "validation_error",
    "errors": [
      {
        "code": "invalid",
        "detail": "Cannot update more than 25 employees at once.",
        "attr": "employee_ids"
      }
    ]
  }
}
```

- **400 Bad Request** - No role selected:

```json
{
  "success": false,
  "data": null,
  "error": {
    "type": "validation_error",
    "errors": [
      {
        "code": "invalid",
        "detail": "Please select a new role.",
        "attr": "new_role_id"
      }
    ]
  }
}
```

- **400 Bad Request** - Invalid employee IDs:

```json
{
  "success": false,
  "data": null,
  "error": {
    "type": "validation_error",
    "errors": [
      {
        "code": "invalid",
        "detail": "One or more employee IDs are invalid.",
        "attr": "employee_ids"
      }
    ]
  }
}
```

---

## Response Format

All responses follow the standardized envelope format:

```json
{
  "success": boolean,
  "data": <response_data>,
  "error": <error_details>
}
```

- `success`: `true` for successful requests (2xx status), `false` for errors (4xx/5xx status)
- `data`: Contains the actual response data (null on errors)
- `error`: Contains error details (null on success)

---

## Pagination

List endpoints support pagination with the following query parameters:

- `page`: Page number (default: 1)
- `page_size`: Results per page (default: system default, typically 30-100)

Paginated responses include:

```json
{
  "success": true,
  "data": {
    "count": 100,
    "next": "http://api.example.com/api/hrm/employee-roles/?page=2",
    "previous": null,
    "results": [...]
  },
  "error": null
}
```

---

## Business Logic Summary

### Employee Listing (QTNV 3.2.1)

1. **Default Sorting**: Employees are sorted by employee code (username) in descending order
2. **Search**: Supports searching by continuous substring match in:
   - Employee first name
   - Employee last name
   - Role name
3. **Filtering**: Supports filtering by:
   - Branch (Chi nhánh)
   - Block (Khối) - requires Branch
   - Department (Phòng ban) - requires Block
   - Position (Chức vụ)
   - Role (Vai trò)
4. **Organizational Data**: Shows employee's primary organizational position (branch, block, department, position)

### Bulk Role Update (QTNV 3.2.4)

1. **Validation**:
   - At least 1 employee must be selected
   - Maximum 25 employees per update
   - New role must be specified
   - All employee IDs must be valid
2. **Session Invalidation**:
   - When an employee's role changes, their active session is cleared
   - Forces user to log out and log back in with new role permissions
3. **Transaction Safety**:
   - All updates are performed within a database transaction
   - If any update fails, all changes are rolled back
4. **Efficiency**:
   - Only employees whose role actually changes are updated
   - Uses bulk SQL UPDATE for performance

---

## Example Frontend Integration

### TypeScript/JavaScript Example

```typescript
// List employees with filters
async function listEmployees(filters: {
  search?: string;
  branch?: number;
  role?: number;
  ordering?: string;
}) {
  const params = new URLSearchParams();
  if (filters.search) params.append('search', filters.search);
  if (filters.branch) params.append('branch', filters.branch.toString());
  if (filters.role) params.append('role', filters.role.toString());
  if (filters.ordering) params.append('ordering', filters.ordering);

  const response = await fetch(`/api/hrm/employee-roles/?${params}`, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
    },
  });

  const result = await response.json();
  return result.data; // Extract data from envelope
}

// Bulk update roles
async function bulkUpdateRoles(employeeIds: number[], newRoleId: number) {
  const response = await fetch('/api/hrm/employee-roles/bulk-update-roles/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      employee_ids: employeeIds,
      new_role_id: newRoleId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error.errors[0].detail);
  }

  const result = await response.json();
  return result.data; // Contains success, message, updated_count
}
```

---

## Testing

Comprehensive test coverage is provided in `apps/hrm/tests/test_employee_role_api.py`:

- List employees with role information
- Default sorting by employee code (descending)
- Search by employee name
- Search by role name
- Case-insensitive search
- Filter by branch, department, role
- Combine search and filters
- Bulk update roles successfully
- Session invalidation after role update
- Validation errors (no selection, too many employees, no role selected)

Run tests:

```bash
ENVIRONMENT=testing poetry run pytest apps/hrm/tests/test_employee_role_api.py -v
```

---

## Version History

- **v1.0** (2025-10-06): Initial implementation
  - Employee listing with search and filters
  - Bulk role update (max 25 employees)
  - Session invalidation on role change
  - Comprehensive test coverage
