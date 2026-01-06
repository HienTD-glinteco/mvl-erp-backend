# Mobile API Reference (v2)

This document provides a quick reference to all new mobile endpoints.

## Base URL

All mobile endpoints are prefixed with `/api/mobile/`

## Authentication

All mobile endpoints require authentication. No additional permissions are needed.

---

## HRM Mobile Endpoints

### My Timesheets

**Base URL:** `/api/mobile/hrm/me/timesheets/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{id}/` | Get my timesheet for a specific month |

**Query Parameters:**
- `month` - Month filter (format: MM/YYYY)

---

### My Attendance Records

**Base URL:** `/api/mobile/hrm/me/attendance-records/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my attendance records |
| GET | `/{id}/` | Get specific attendance record |

**Query Parameters:**
- `date` - Filter by date
- `date__gte` - Filter by date greater than or equal
- `date__lte` - Filter by date less than or equal

---

### My Proposals (All Types)

**Base URL:** `/api/mobile/hrm/me/proposals/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all my proposals (all types) |
| GET | `/{id}/` | Get specific proposal details |

---

### My Maternity Leave Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/maternity-leave/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my maternity leave proposals |
| POST | `/` | Create new maternity leave proposal |
| GET | `/{id}/` | Get maternity leave proposal details |
| PATCH | `/{id}/` | Update maternity leave proposal (draft only) |
| DELETE | `/{id}/` | Delete maternity leave proposal (draft only) |

---

### My Unpaid Leave Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/unpaid-leave/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my unpaid leave proposals |
| POST | `/` | Create new unpaid leave proposal |
| GET | `/{id}/` | Get unpaid leave proposal details |
| PATCH | `/{id}/` | Update unpaid leave proposal (draft only) |
| DELETE | `/{id}/` | Delete unpaid leave proposal (draft only) |

---

### My Paid Leave Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/paid-leave/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my paid leave proposals |
| POST | `/` | Create new paid leave proposal |
| GET | `/{id}/` | Get paid leave proposal details |
| PATCH | `/{id}/` | Update paid leave proposal (draft only) |
| DELETE | `/{id}/` | Delete paid leave proposal (draft only) |

---

### My Post-Maternity Benefits Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/post-maternity-benefits/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my post-maternity benefits proposals |
| POST | `/` | Create new post-maternity benefits proposal |
| GET | `/{id}/` | Get post-maternity benefits proposal details |
| PATCH | `/{id}/` | Update post-maternity benefits proposal (draft only) |
| DELETE | `/{id}/` | Delete post-maternity benefits proposal (draft only) |

---

### My Overtime Work Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/overtime-work/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my overtime work proposals |
| POST | `/` | Create new overtime work proposal |
| GET | `/{id}/` | Get overtime work proposal details |
| PATCH | `/{id}/` | Update overtime work proposal (draft only) |
| DELETE | `/{id}/` | Delete overtime work proposal (draft only) |

---

### My Late Exemption Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/late-exemption/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my late exemption proposals |
| POST | `/` | Create new late exemption proposal |
| GET | `/{id}/` | Get late exemption proposal details |
| PATCH | `/{id}/` | Update late exemption proposal (draft only) |
| DELETE | `/{id}/` | Delete late exemption proposal (draft only) |

---

### My Job Transfer Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/job-transfer/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my job transfer proposals |
| POST | `/` | Create new job transfer proposal |
| GET | `/{id}/` | Get job transfer proposal details |
| PATCH | `/{id}/` | Update job transfer proposal (draft only) |
| DELETE | `/{id}/` | Delete job transfer proposal (draft only) |

---

### My Device Change Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/device-change/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my device change proposals |
| POST | `/` | Create new device change proposal |
| GET | `/{id}/` | Get device change proposal details |
| PATCH | `/{id}/` | Update device change proposal (draft only) |
| DELETE | `/{id}/` | Delete device change proposal (draft only) |

---

### My Asset Allocation Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/asset-allocation/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my asset allocation proposals |
| POST | `/` | Create new asset allocation proposal |
| GET | `/{id}/` | Get asset allocation proposal details |
| PATCH | `/{id}/` | Update asset allocation proposal (draft only) |
| DELETE | `/{id}/` | Delete asset allocation proposal (draft only) |

---

### My Timesheet Entry Complaint Proposals

**Base URL:** `/api/mobile/hrm/me/proposals/timesheet-entry-complaint/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List my timesheet entry complaint proposals |
| POST | `/` | Create new timesheet entry complaint proposal |
| GET | `/{id}/` | Get timesheet entry complaint proposal details |
| PATCH | `/{id}/` | Update timesheet entry complaint proposal (draft only) |
| DELETE | `/{id}/` | Delete timesheet entry complaint proposal (draft only) |

---

### Pending Verifications

**Base URL:** `/api/mobile/hrm/me/pending-verifications/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List proposals pending my verification |
| GET | `/{id}/` | Get pending verification details |
| POST | `/{id}/verify/` | Verify a proposal |
| POST | `/{id}/reject/` | Reject a proposal verification |

**Request Body for Verify/Reject:**
```json
{
  "note": "Verification or rejection note"
}
```

---

## Payroll Mobile Endpoints

### My KPI Assessments

**Base URL:** `/api/mobile/payroll/me/kpi-assessments/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all my KPI assessments |
| GET | `/{id}/` | Get specific KPI assessment details |
| PATCH | `/{id}/` | Update my KPI self-assessment |
| GET | `/current/` | Get current unfinalized KPI assessment |

**Request Body for Update:**
```json
{
  "plan_tasks": "My planned tasks",
  "extra_tasks": "Extra tasks handled",
  "proposal": "My improvement suggestions",
  "items": [
    {"item_id": 1, "score": "85.00"},
    {"item_id": 2, "score": "90.50"}
  ]
}
```

---

### My Team KPI Assessments (Manager)

**Base URL:** `/api/mobile/payroll/me/team-kpi-assessments/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all team member KPI assessments |
| GET | `/{id}/` | Get team member KPI assessment details |
| PATCH | `/{id}/` | Update team member KPI assessment |
| GET | `/current/` | Get current unfinalized team assessments |

**Request Body for Update:**
```json
{
  "manager_assessment": "Manager feedback",
  "grade": "B",
  "items": [
    {"item_id": 1, "score": "80.00"},
    {"item_id": 2, "score": "85.00"}
  ]
}
```

---

## Common Query Parameters

All list endpoints support:
- `page` - Page number for pagination
- `page_size` - Number of items per page
- `ordering` - Sort by field (prefix with `-` for descending)
- `search` - Search by code, name, etc.

---

## Response Format

All endpoints return data in the standard envelope format:

**Success:**
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

**Error:**
```json
{
  "success": false,
  "data": null,
  "error": {
    "field_name": ["Error message"]
  }
}
```

---

## Migration from Old Endpoints

Old endpoints are still available for backward compatibility:

- Old: `/api/mobile/hrm/proposals/mine/`
- New: `/api/mobile/hrm/me/proposals/`

- Old: `/api/mobile/hrm/timesheets/mine/`
- New: `/api/mobile/hrm/me/timesheets/{id}/`

- Old: `/api/mobile/hrm/proposal-verifiers/mine/`
- New: `/api/mobile/hrm/me/pending-verifications/`

Old endpoints will be deprecated in a future release.

---

## Notes

1. All mobile endpoints require authentication
2. No additional permissions are required - users can only access their own data
3. Draft proposals can be updated/deleted; submitted proposals cannot
4. For API documentation, see `/docs/mobile/` (development environment only)
