# Penalty Ticket API Documentation

## Overview

The Penalty Management module now exposes simple CRUD operations for penalty tickets (uniform violations). Each ticket stores the payroll period, penalty month, employee snapshot information, amount, notes, and optional attachments.

## Base URL

All API endpoints are prefixed with `/api/payroll/`.

## Authentication

All endpoints require authentication. Include the authentication token in the request header:

```
Authorization: Bearer <your-token>
```

## Response Format

All API responses follow the envelope format:

**Success Response:**

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

**Error Response:**

```json
{
  "success": false,
  "data": null,
  "error": {
    "field_name": ["Error message"],
    "detail": "General error message"
  }
}
```

## Endpoints

### 1. List Penalty Tickets

Retrieve a paginated list of penalty tickets with filters and search.

**Endpoint:** `GET /api/payroll/penalty-tickets`

**Query Parameters:**

- `period`: Filter by period in MM/YYYY format
- `month`: Filter by penalty month in MM/YYYY format
- `employee`: Filter by employee ID
- `employee_code`: Filter by employee code
- `amount_min` / `amount_max`: Filter by amount range
- `search`: Search by code, employee_code, employee_name
- `page` / `page_size`: Pagination controls

**Example Response:**

```json
{
  "success": true,
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "code": "RVF-202511-0001",
        "period": "11/2025",
        "month": "11/2025",
        "employee": "ab12cdef-0000-0000-0000-000000000001",
        "employee_code": "E0001",
        "employee_name": "John Doe",
        "amount": 100000,
        "note": "Uniform violation - missing name tag",
        "attachment": null,
        "created_at": "2025-11-15T10:00:00Z",
        "updated_at": "2025-11-15T10:00:00Z"
      }
    ]
  },
  "error": null
}
```

### 2. Create Penalty Ticket

Create a new penalty ticket. The ticket code is generated automatically.

**Endpoint:** `POST /api/payroll/penalty-tickets`

**Request Body:**

```json
{
  "period": "11/2025",
  "month": "11/2025",
  "employee": "ab12cdef-0000-0000-0000-000000000001",
  "amount": 100000,
  "note": "Uniform violation - missing name tag"
}
```

**Example Success Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "code": "RVF-202511-0001",
    "period": "11/2025",
    "month": "11/2025",
    "employee": "ab12cdef-0000-0000-0000-000000000001",
    "employee_code": "E0001",
    "employee_name": "John Doe",
    "amount": 100000,
    "note": "Uniform violation - missing name tag",
    "attachment": null,
    "created_at": "2025-11-15T10:00:00Z",
    "updated_at": "2025-11-15T10:00:00Z"
  },
  "error": null
}
```

### 3. Update Penalty Ticket

Update an existing penalty ticket. The `code`, `employee_code`, and `employee_name` are read-only snapshots.

**Endpoint:** `PUT /api/payroll/penalty-tickets/{id}`

**Request Body:**

```json
{
  "period": "11/2025",
  "month": "11/2025",
  "employee": "ab12cdef-0000-0000-0000-000000000001",
  "amount": 120000,
  "note": "Updated note"
}
```

### 4. Delete Penalty Ticket

Remove a penalty ticket by ID.

**Endpoint:** `DELETE /api/payroll/penalty-tickets/{id}`

**Example Response:**

```json
{
  "success": true,
  "data": null,
  "error": null
}
```

---

### 5. List Penalty Tickets

Retrieve a paginated list of penalty tickets (uniform violations).

**Endpoint:** `GET /api/payroll/penalty-tickets`

**Query Parameters:**

- `period`: Filter by period (MM/YYYY format)
- `employee`: Filter by employee ID
- `employee_code`: Filter by employee code
- `org_department`: Filter by department
- `amount_vnd_min`: Minimum amount
- `amount_vnd_max`: Maximum amount
- `occurred_at_after`: Filter occurred date (after)
- `occurred_at_before`: Filter occurred date (before)
- `search`: Search by code, employee code, or name
- `page`: Page number
- `page_size`: Results per page

**Example Request:**

```bash
GET /api/payroll/penalty-tickets?period=11/2025&org_department=Sales
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "code": "RVF-202511-0001",
        "period": "11/2025",
        "employee": 123,
        "employee_code": "E0001",
        "employee_name": "John Doe",
        "org_branch": "Branch A",
        "org_block": "Block 1",
        "org_department": "Sales",
        "position_title": "Sales Executive",
        "amount_vnd": 100000,
        "occurred_at": "12/11/2025",
        "note": "Uniform violation - missing name tag",
        "attachment": null,
        "created_at": "2025-11-15T10:00:00Z",
        "updated_at": "2025-11-15T10:00:00Z"
      }
    ]
  },
  "error": null
}
```

---

### 6. Get Penalty Ticket Details

Retrieve details of a specific penalty ticket.

**Endpoint:** `GET /api/payroll/penalty-tickets/{id}`

**Example Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "code": "RVF-202511-0001",
    "period": "11/2025",
    "employee": 123,
    "employee_code": "E0001",
    "employee_name": "John Doe",
    "org_branch": "Branch A",
    "org_block": "Block 1",
    "org_department": "Sales",
    "position_title": "Sales Executive",
    "amount_vnd": 100000,
    "occurred_at": "12/11/2025",
    "note": "Uniform violation - missing name tag",
    "attachment": null
  },
  "error": null
}
```

---

### 7. Create Penalty Ticket

Create a new penalty ticket for uniform violation.

**Endpoint:** `POST /api/payroll/penalty-tickets`

**Request Body:**

```json
{
  "period": "11/2025",
  "employee": 123,
  "amount_vnd": 100000,
  "occurred_at": "12/11/2025",
  "note": "Uniform violation - missing name tag"
}
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "code": "RVF-202511-0001",
    "period": "11/2025",
    "employee": 123,
    "employee_code": "E0001",
    "employee_name": "John Doe",
    "org_branch": "Branch A",
    "org_block": "Block 1",
    "org_department": "Sales",
    "amount_vnd": 100000,
    "occurred_at": "12/11/2025",
    "note": "Uniform violation - missing name tag"
  },
  "error": null
}
```

---

### 8. Update Penalty Ticket

Update an existing penalty ticket.

**Endpoint:** `PUT /api/payroll/penalty-tickets/{id}`

**Request Body:**

```json
{
  "period": "11/2025",
  "employee": 123,
  "amount_vnd": 150000,
  "occurred_at": "12/11/2025",
  "note": "Updated note"
}
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "code": "RVF-202511-0001",
    "period": "11/2025",
    "employee": 123,
    "amount_vnd": 150000,
    "occurred_at": "12/11/2025",
    "note": "Updated note"
  },
  "error": null
}
```

---

### 9. Delete Penalty Ticket

Delete a penalty ticket.

**Endpoint:** `DELETE /api/payroll/penalty-tickets/{id}`

**Example Response:**

```
HTTP 204 No Content
```

---

## Business Rules

### Fine Calculations

1. **Late Fine:** `max(late_count - 2, 0) × 50,000 VND`

   - First 2 late days are free
   - Each additional late day costs 50,000 VND

2. **Absence Fine:** `absence_count × 100,000 VND`

   - Each unexcused absence costs 100,000 VND

3. **Total Fine:** Sum of late fine, absence fine, and uniform violation fine

### Payroll Integration

- When a penalty ticket is created/updated/deleted, the affected employee's penalty board `status` is reset to `NOT_CALCULATED`
- When monthly payroll is created, all penalty boards for that period are marked as `CALCULATED`

### Code Generation

- Penalty ticket codes follow format: `RVF-{YYYYMM}-{seq}`
- Example: `RVF-202511-0001`
- Sequence numbers are zero-padded to 4 digits

## Error Codes

| HTTP Status | Error Code            | Description                       |
| ----------- | --------------------- | --------------------------------- |
| 400         | Bad Request           | Invalid input or validation error |
| 401         | Unauthorized          | Missing or invalid authentication |
| 403         | Forbidden             | Insufficient permissions          |
| 404         | Not Found             | Resource not found                |
| 500         | Internal Server Error | Server error                      |

## Permissions

Each endpoint requires specific permissions:

- `payroll.view_penalty_board` - View penalty boards
- `payroll.mark_penalty_paid` - Mark penalties as paid
- `payroll.mark_penalty_unpaid` - Mark penalties as unpaid
- `payroll.export_penalty_board` - Export penalty boards
- `payroll.upload_penalty_data` - Upload uniform violation data
- `payroll.view_penalty_ticket` - View penalty tickets
- `payroll.add_penalty_ticket` - Create penalty tickets
- `payroll.change_penalty_ticket` - Update penalty tickets
- `payroll.delete_penalty_ticket` - Delete penalty tickets
