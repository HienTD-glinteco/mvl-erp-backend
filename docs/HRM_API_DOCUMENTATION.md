# HRM API Documentation

## Overview

This document provides comprehensive API documentation for the HRM (Human Resource Management) organizational chart subsystem. The API enables management of company organizational structure including branches, blocks, departments, and positions.

## Base URL

```
/api/hrm/
```

## Authentication

All API endpoints require authentication using JWT tokens in the Authorization header:

```
Authorization: Bearer <token>
```

## Response Format

All API responses are wrapped in a standard envelope format:

```json
{
  "success": true,
  "data": <actual_response_data>,
  "error": null
}
```

For error responses:

```json
{
  "success": false,
  "data": null,
  "error": "Error message"
}
```

---

## Endpoints

### 1. Branches (Chi nhánh)

#### List Branches
- **GET** `/api/hrm/branches/`
- **Description**: Get list of all branches
- **Query Parameters**:
  - `search` (string): Search by name, code, or address
  - `is_active` (boolean): Filter by active status
  - `page` (integer): Page number for pagination
  - `page_size` (integer): Number of items per page

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "Chi nhánh Hà Nội",
      "code": "HN",
      "address": "123 Lê Duẩn, Hà Nội",
      "phone": "0243456789",
      "email": "hanoi@maivietland.com",
      "is_active": true,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

#### Create Branch
- **POST** `/api/hrm/branches/`
- **Description**: Create a new branch

**Request Body:**
```json
{
  "name": "Chi nhánh TP.HCM",
  "code": "HCM",
  "address": "456 Nguyễn Huệ, TP.HCM",
  "phone": "0283456789",
  "email": "hcm@maivietland.com"
}
```

#### Get Branch Details
- **GET** `/api/hrm/branches/{id}/`
- **Description**: Get detailed information about a specific branch

#### Update Branch
- **PUT/PATCH** `/api/hrm/branches/{id}/`
- **Description**: Update branch information

#### Delete Branch
- **DELETE** `/api/hrm/branches/{id}/`
- **Description**: Delete a branch

---

### 2. Blocks (Khối)

#### List Blocks
- **GET** `/api/hrm/blocks/`
- **Description**: Get list of all blocks
- **Query Parameters**:
  - `search` (string): Search by name, code, or description
  - `block_type` (string): Filter by block type (`support` or `business`)
  - `branch` (uuid): Filter by branch ID
  - `branch_code` (string): Filter by branch code
  - `is_active` (boolean): Filter by active status

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "Khối Kinh doanh",
      "code": "KD",
      "block_type": "business",
      "block_type_display": "Khối kinh doanh",
      "branch": "branch_uuid",
      "branch_name": "Chi nhánh Hà Nội",
      "description": "Khối phụ trách hoạt động kinh doanh",
      "is_active": true,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

### 3. Departments (Phòng ban)

#### List Departments
- **GET** `/api/hrm/departments/`
- **Description**: Get list of all departments
- **Query Parameters**:
  - `search` (string): Search by name, code, or description
  - `block` (uuid): Filter by block ID
  - `block_type` (string): Filter by block type
  - `function` (string): Filter by department function
  - `is_main_department` (boolean): Filter main departments
  - `parent_department` (uuid): Filter by parent department
  - `has_parent` (boolean): Filter departments with/without parent

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "Phòng Kinh doanh 1",
      "code": "KD01",
      "block": "block_uuid",
      "block_name": "Khối Kinh doanh",
      "block_type": "business",
      "parent_department": null,
      "parent_department_name": null,
      "function": "business",
      "function_display": "Kinh doanh",
      "is_main_department": true,
      "management_department": null,
      "management_department_name": null,
      "full_hierarchy": "Phòng Kinh doanh 1",
      "available_function_choices": [
        ["business", "Kinh doanh"]
      ],
      "available_management_departments": [],
      "description": "",
      "is_active": true,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

#### Create Department
- **POST** `/api/hrm/departments/`
- **Description**: Create a new department

**Request Body:**
```json
{
  "name": "Phòng Nhân sự",
  "code": "NS",
  "block": "block_uuid",
  "function": "hr_admin",
  "is_main_department": true,
  "management_department": null,
  "description": "Phòng quản lý nhân sự"
}
```

**Business Logic:**
- If `block` has type "business", `function` is automatically set to "business"
- If `block` has type "support", `function` must be selected from available options
- Only one department can be marked as `is_main_department` per function
- `management_department` must be in the same block and have the same function

#### Get Department Tree
- **GET** `/api/hrm/departments/tree/`
- **Description**: Get hierarchical tree structure of departments
- **Query Parameters**:
  - `block_id` (uuid): Filter departments by block

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "Phòng Nhân sự",
      "code": "NS",
      "children": [
        {
          "id": "uuid",
          "name": "Ban Tuyển dụng",
          "code": "TD",
          "children": []
        }
      ]
    }
  ]
}
```

#### Get Function Choices
- **GET** `/api/hrm/departments/function_choices/`
- **Description**: Get available function choices based on block type
- **Query Parameters**:
  - `block_type` (string, required): Block type (`support` or `business`)

**Example Response for Support Block:**
```json
{
  "success": true,
  "data": {
    "block_type": "support",
    "functions": [
      {"value": "hr_admin", "label": "Hành chính Nhân sự"},
      {"value": "recruit_training", "label": "Tuyển dụng - Đào tạo"},
      {"value": "marketing", "label": "Marketing"},
      {"value": "business_secretary", "label": "Thư ký Kinh doanh"},
      {"value": "accounting", "label": "Kế toán"},
      {"value": "trading_floor", "label": "Sàn liên kết"},
      {"value": "project_promotion", "label": "Xúc tiến Dự án"},
      {"value": "project_development", "label": "Phát triển Dự án"}
    ]
  }
}
```

**Example Response for Business Block:**
```json
{
  "success": true,
  "data": {
    "block_type": "business",
    "functions": [
      {"value": "business", "label": "Kinh doanh"}
    ]
  }
}
```

#### Get Management Department Choices
- **GET** `/api/hrm/departments/management_choices/`
- **Description**: Get available management departments for selection
- **Query Parameters**:
  - `block_id` (uuid, required): Block ID
  - `function` (string, required): Department function

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "Phòng Nhân sự chính",
      "code": "NS01",
      "full_path": "Chi nhánh Hà Nội/Khối Hỗ trợ/Phòng Nhân sự chính"
    }
  ]
}
```

---

### 4. Positions (Chức vụ)

#### List Positions
- **GET** `/api/hrm/positions/`
- **Description**: Get list of all positions ordered by level
- **Query Parameters**:
  - `search` (string): Search by name, code, or description
  - `level` (integer): Filter by specific level
  - `level_gte` (integer): Filter by minimum level
  - `level_lte` (integer): Filter by maximum level
  - `is_active` (boolean): Filter by active status

**Position Levels:**
1. CEO (Tổng Giám đốc)
2. DIRECTOR (Giám đốc khối)
3. DEPUTY_DIRECTOR (Phó Giám đốc khối)
4. MANAGER (Trưởng phòng)
5. DEPUTY_MANAGER (Phó Trưởng phòng)
6. SUPERVISOR (Giám sát)
7. STAFF (Nhân viên)
8. INTERN (Thực tập sinh)

---

### 5. Organization Chart (Sơ đồ tổ chức)

#### List Organization Chart Entries
- **GET** `/api/hrm/organization-chart/`
- **Description**: Get list of all organization chart entries
- **Query Parameters**:
  - `employee` (uuid): Filter by employee ID
  - `employee_username` (string): Filter by employee username
  - `position` (uuid): Filter by position ID
  - `position_level` (integer): Filter by position level
  - `department` (uuid): Filter by department ID
  - `block` (uuid): Filter by block ID
  - `branch` (uuid): Filter by branch ID
  - `is_current` (boolean): Filter current assignments (no end date)
  - `is_primary` (boolean): Filter primary positions
  - `start_date` (date): Filter by start date
  - `end_date` (date): Filter by end date

#### Get Organization Hierarchy
- **GET** `/api/hrm/organization-chart/hierarchy/`
- **Description**: Get complete organizational structure
- **Query Parameters**:
  - `branch_id` (uuid): Filter by branch
  - `block_id` (uuid): Filter by block
  - `department_id` (uuid): Filter by specific department

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "department": {
        "id": "uuid",
        "name": "Phòng Kinh doanh 1",
        "code": "KD01",
        "full_hierarchy": "Phòng Kinh doanh 1",
        "block": {
          "id": "uuid",
          "name": "Khối Kinh doanh",
          "code": "KD",
          "block_type": "business",
          "branch": {
            "id": "uuid",
            "name": "Chi nhánh Hà Nội",
            "code": "HN"
          }
        }
      },
      "positions": [
        {
          "id": "uuid",
          "employee": {
            "id": "uuid",
            "username": "nguyen.van.a",
            "full_name": "Nguyễn Văn A",
            "email": "nguyen.van.a@maivietland.com"
          },
          "position": {
            "id": "uuid",
            "name": "Trưởng phòng",
            "code": "TP",
            "level": 4
          },
          "start_date": "2025-01-01",
          "end_date": null,
          "is_primary": true,
          "is_active": true
        }
      ]
    }
  ]
}
```

#### Get Employees by Department
- **GET** `/api/hrm/organization-chart/by_department/`
- **Description**: Get all employees in a specific department
- **Query Parameters**:
  - `department_id` (uuid, required): Department ID

---

### 6. Recruitment Channels (Kênh tuyển dụng)

#### List Recruitment Channels
- **GET** `/api/hrm/recruitment-channels/`
- **Description**: Get list of all recruitment channels ordered by creation time (descending)
- **Query Parameters**:
  - `search` (string): Search by name, code, or description
  - `name` (string): Filter by name (case-insensitive contains)
  - `code` (string): Filter by code (case-insensitive contains)
  - `belong_to` (string): Filter by belong to (choices: `job_website`, `marketing`)
  - `is_active` (boolean): Filter by active status

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "LinkedIn",
      "code": "LINKEDIN",
      "belong_to": "job_website",
      "belong_to_display": "Job Website",
      "description": "Professional networking platform",
      "is_active": true,
      "created_at": "2025-01-20T10:00:00Z",
      "updated_at": "2025-01-20T10:00:00Z"
    }
  ]
}
```

#### Create Recruitment Channel
- **POST** `/api/hrm/recruitment-channels/`
- **Description**: Create a new recruitment channel
- **Required Fields**:
  - `name` (string, max 200 chars): Channel name
  - `code` (string, max 50 chars, unique): Channel code
- **Optional Fields**:
  - `belong_to` (string, default: `marketing`): Channel belongs to (choices: `job_website`, `marketing`)
  - `description` (string): Channel description
  - `is_active` (boolean, default: true): Active status

**Request Body:**
```json
{
  "name": "LinkedIn",
  "code": "LINKEDIN",
  "belong_to": "job_website",
  "description": "Professional networking platform",
  "is_active": true
}
```

#### Get Recruitment Channel Details
- **GET** `/api/hrm/recruitment-channels/{id}/`
- **Description**: Get detailed information about a specific recruitment channel

#### Update Recruitment Channel
- **PUT** `/api/hrm/recruitment-channels/{id}/`
- **Description**: Update all fields of a recruitment channel
- **PATCH** `/api/hrm/recruitment-channels/{id}/`
- **Description**: Partially update a recruitment channel

#### Delete Recruitment Channel
- **DELETE** `/api/hrm/recruitment-channels/{id}/`
- **Description**: Delete a recruitment channel
- **Response**: 204 No Content on success

---

## Error Handling

### Common Error Codes

- **400 Bad Request**: Invalid request data or missing required parameters
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation errors

### Validation Errors

**Example validation error response:**
```json
{
  "success": false,
  "data": null,
  "error": {
    "function": ["Chức năng này không phù hợp với loại khối Khối kinh doanh."],
    "is_main_department": ["Đã có phòng ban đầu mối cho chức năng Kinh doanh."]
  }
}
```

---

## Business Rules Summary

### Department Function Rules
1. **Business Blocks**: Automatically set function to "Kinh doanh" (business)
2. **Support Blocks**: Must select from 8 predefined functions:
   - Hành chính Nhân sự
   - Tuyển dụng - Đào tạo
   - Marketing
   - Thư ký Kinh doanh
   - Kế toán
   - Sàn liên kết
   - Xúc tiến Dự án
   - Phát triển Dự án

### Main Department Rules
- Only one department can be marked as "main department" per function
- Main departments are typically the highest-level departments for each function

### Management Department Rules
- Management department must be in the same block
- Management department must have the same function
- Departments can manage other departments within the same functional area

### Hierarchy Rules
- Departments can have parent-child relationships
- Parent department must be in the same block
- Unlimited nesting levels supported
- Full hierarchy path automatically generated

---

## Pagination

All list endpoints support pagination with the following query parameters:
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 20, max: 100)

**Paginated Response Format:**
```json
{
  "success": true,
  "data": {
    "count": 100,
    "next": "/api/hrm/departments/?page=3",
    "previous": "/api/hrm/departments/?page=1",
    "results": [...]
  }
}
```

---

## Filtering and Search

### Search
Use the `search` parameter to perform full-text search across:
- Names, codes, descriptions for most models
- Employee usernames, names for organization chart

### Filtering
Each endpoint supports specific filters as documented above. Filters can be combined:

```
GET /api/hrm/departments/?block_type=support&function=hr_admin&is_active=true
```

### Ordering
Use the `ordering` parameter to sort results:

```
GET /api/hrm/positions/?ordering=level
GET /api/hrm/departments/?ordering=-created_at
```

---

This API provides a comprehensive solution for managing organizational structure with Vietnamese business requirements, including proper validation, hierarchical relationships, and business logic enforcement.
