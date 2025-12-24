# Recovery/Back Pay Management Module (II.2)

## Overview

This module implements comprehensive CRUD operations for recovery and back pay vouchers in the payroll system, enabling organizations to manage salary adjustments for employees.

## Features

### Core Functionality

1. **CRUD Operations**
   - Create recovery/back pay vouchers with automatic code generation
   - Read/List vouchers with pagination (25 per page)
   - Update vouchers (resets status to NOT_CALCULATED)
   - Delete vouchers (with payroll guard check)

2. **Code Generation**
   - Auto-generates unique codes in format: `RV-{YYYYMM}-{seq}`
   - Example: `RV-202509-0001` for the first voucher in September 2025
   - Sequential numbering per month

3. **Search & Filtering**
   - Phrase search across: code, name, employee_code, employee_name
   - Filter by: voucher_type, status, employee_id, period, amount range
   - Default sort: latest updated first

4. **Export**
   - Export to XLSX format
   - Respects all applied filters
- Columns: code, name, voucher_type, employee (nested id/code/fullname), block, branch, department, position, employee_code, employee_name, amount, month, status, note

## Models

### RecoveryVoucher

Core model for recovery and back pay vouchers.

**Fields:**
- `id`: Auto-generated UUID primary key
- `code`: Unique code (format: RV-{YYYYMM}-{seq})
- `name`: Descriptive name (max 250 chars)
- `voucher_type`: RECOVERY or BACK_PAY
- `employee`: Foreign key to Employee
- `employee_code`: Cached employee code for search
- `employee_name`: Cached employee name for search
- `amount`: Amount in Vietnamese Dong (integer, must be > 0)
- `month`: Period stored as first day of the month (stored as date)
- `status`: NOT_CALCULATED or CALCULATED
- `note`: Optional notes (SafeTextField, max 500 chars)
- `created_by`: User who created the voucher
- `updated_by`: User who last updated the voucher
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

**Indexes:**
- (month, employee)
- (status)
- (-updated_at)

**Business Rules:**
- Amount must be greater than 0
- Employee must be active or onboarding
- Status automatically set to NOT_CALCULATED on create
- Status reset to NOT_CALCULATED on update
- Employee fields (code, name) cached on save

## API Endpoints

### List Vouchers
```
GET /api/payroll/recovery-vouchers/
```

**Query Parameters:**
- `search`: Search across code, name, employee_code, employee_name
- `voucher_type`: Filter by type (RECOVERY, BACK_PAY)
- `status`: Filter by status (NOT_CALCULATED, CALCULATED)
- `employee_id`: Filter by employee UUID
- `period`: Filter by period in MM/YYYY format
- `amount_min`: Minimum amount
- `amount_max`: Maximum amount
- `ordering`: Sort by fields (e.g., `-updated_at`, `amount`)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 25, max: 100)

**Response:**
```json
{
  "success": true,
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "uuid",
        "code": "RV-202509-0001",
        "name": "September back pay",
        "voucher_type": "BACK_PAY",
        "voucher_type_display": "Back Pay",
        "employee": {
          "id": "e5d8f1a3-...",
          "code": "E0001",
          "fullname": "John Doe"
        },
        "block": null,
        "branch": null,
        "department": null,
        "position": null,
        "employee_code": "E0001",
        "employee_name": "John Doe",
        "amount": 1500000,
        "month": "09/2025",
        "status": "NOT_CALCULATED",
        "status_display": "Not Calculated",
        "note": "Adjustment for commission",
        "created_at": "2025-09-10T10:00:00Z",
        "updated_at": "2025-09-10T10:00:00Z"
      }
    ]
  },
  "error": null
}
```

### Retrieve Voucher
```
GET /api/payroll/recovery-vouchers/{id}/
```

**Response:** Single voucher with all fields, including nested employee (code/fullname), block, branch, department, position, and audit fields.

### Create Voucher
```
POST /api/payroll/recovery-vouchers/
```

**Request Body:**
```json
{
  "name": "September back pay",
  "voucher_type": "BACK_PAY",
  "employee_id": "uuid",
  "amount": 1500000,
  "month": "09/2025",
  "note": "Adjustment for commission"
}
```

**Validations:**
- `name`: Required, max 250 chars
- `voucher_type`: Required, must be RECOVERY or BACK_PAY
- `employee_id`: Required, must exist and be active/onboarding
- `amount`: Required, must be > 0
- `month`: Required, format MM/YYYY
- `note`: Optional, max 500 chars

**Response:** Created voucher with auto-generated code and status NOT_CALCULATED

### Update Voucher
```
PUT /api/payroll/recovery-vouchers/{id}/
PATCH /api/payroll/recovery-vouchers/{id}/
```

**Request Body:** Same as create (all fields for PUT, partial for PATCH)

**Behavior:**
- Status automatically reset to NOT_CALCULATED
- Code and ID are immutable
- Employee fields recached

### Delete Voucher
```
DELETE /api/payroll/recovery-vouchers/{id}/
```

**Guard:** Deletion blocked if payroll table exists for the voucher's period (returns 409 Conflict)

**Response:** 204 No Content on success

### Export Vouchers
```
GET /api/payroll/recovery-vouchers/download/
```

**Query Parameters:** Same as list endpoint

**Response:** XLSX file or presigned S3 URL

## Usage Examples

### Creating a Recovery Voucher

```python
import requests

url = "https://api.example.com/api/payroll/recovery-vouchers/"
headers = {"Authorization": "Bearer <token>"}
data = {
    "name": "September salary recovery",
    "voucher_type": "RECOVERY",
    "employee_id": "employee-uuid",
    "amount": 500000,
    "month": "09/2025",
    "note": "Excess payment recovery"
}

response = requests.post(url, headers=headers, json=data)
voucher = response.json()["data"]
print(f"Created voucher: {voucher['code']}")
```

### Searching and Filtering

```python
# Search by employee name
response = requests.get(
    f"{url}?search=John Doe",
    headers=headers
)

# Filter by type and period
response = requests.get(
    f"{url}?voucher_type=BACK_PAY&period=09/2025",
    headers=headers
)

### cURL Examples

```bash
curl -X POST https://api.example.com/api/payroll/recovery-vouchers/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "December back pay",
  "voucher_type": "BACK_PAY",
  "employee_id": "employee-uuid",
  "amount": 1200000,
  "month": "12/2025",
  "note": "Curl sample request"
  }'
```

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "code": "RV-202512-0001",
    "name": "December back pay",
    "voucher_type": "BACK_PAY",
    "voucher_type_display": "Back Pay",
    "employee": {
      "id": "employee-uuid",
      "code": "E0001",
      "fullname": "John Doe"
    },
    "block": null,
    "branch": null,
    "department": null,
    "position": null,
    "employee_code": "E0001",
    "employee_name": "John Doe",
    "amount": 1200000,
    "month": "12/2025",
    "status": "NOT_CALCULATED",
    "status_display": "Not Calculated",
    "note": "Curl sample request"
  },
  "error": null
}
```

```bash
curl "https://api.example.com/api/payroll/recovery-vouchers/?period=12/2025" \
  -H "Authorization: Bearer <token>"
```

```json
{
  "success": true,
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "uuid",
        "code": "RV-202512-0001",
        "name": "December back pay",
        "voucher_type": "BACK_PAY",
        "amount": 1200000,
        "period": "2025-12-01",
        "note": "Curl sample request"
      }
    ]
  },
  "error": null
}
```

# Filter by amount range
response = requests.get(
    f"{url}?amount_min=1000000&amount_max=2000000",
    headers=headers
)
```

### Exporting Vouchers

```python
# Export all back pay vouchers for September 2025
response = requests.get(
    f"{url}download/?voucher_type=BACK_PAY&period=09/2025",
    headers=headers
)
```

## Testing

Comprehensive test coverage includes:

### Model Tests (`test_recovery_voucher_model.py`)
- Creation with valid data
- Employee field caching
- Voucher type and status choices
- Amount validation
- Unique code constraint
- String representation
- Ordering

### Serializer Tests (`test_recovery_voucher_serializers.py`)
- Serialization
- Period string validation
- Employee validation (active/inactive)
- Amount validation
- Name and note validation

### API Tests (`test_recovery_voucher_api.py`)
- List (empty, with data, search, filters)
- Retrieve (success, not found)
- Create (success, validations)
- Update (full, partial)
- Delete (success, not found)
- Code generation format
- Employee field caching

Run tests:
```bash
ENVIRONMENT=test pytest apps/payroll/tests/test_recovery_voucher*.py -v
```

## Django Admin

Access via `/admin/payroll/recoveryvoucher/`

**Features:**
- List view with all key fields
- Search by code, name, employee
- Filter by type, status, period, date
- Read-only code and cached fields
- Audit information in collapsed section
- Auto-set created_by/updated_by on save

## Permissions

All endpoints use Role-Based Access Control (RBAC) with permission prefix `recovery_voucher`:
- `recovery_voucher.list`
- `recovery_voucher.retrieve`
- `recovery_voucher.create`
- `recovery_voucher.update`
- `recovery_voucher.destroy`
- `recovery_voucher.download`

## Integration Points

### Future Integrations

1. **Payroll Table Integration**
   - When payroll created for a month, set vouchers to CALCULATED
   - Include voucher amounts in payroll calculations
   - Prevent deletion if payroll exists

2. **Employee Integration**
   - Already integrated with Employee model
   - Validates employee status (active/onboarding)
   - Caches employee fields for performance

3. **Notification Integration**
   - Notify HR when vouchers created/updated
   - Notify employees about adjustments

## Database Migration

Migration file: `0008_add_recovery_voucher_models.py`

Run migration:
```bash
python manage.py migrate payroll
```

## Files Added/Modified

### New Files
- `apps/payroll/models/recovery_voucher.py` - Models
- `apps/payroll/signals.py` - Signal handlers
- `apps/payroll/api/serializers/recovery_voucher.py` - Serializers
- `apps/payroll/api/filtersets/recovery_voucher.py` - FilterSet
- `apps/payroll/api/views/recovery_voucher.py` - ViewSet
- `apps/payroll/migrations/0008_add_recovery_voucher_models.py` - Migration
- `apps/payroll/tests/test_recovery_voucher_model.py` - Model tests
- `apps/payroll/tests/test_recovery_voucher_serializers.py` - Serializer tests
- `apps/payroll/tests/test_recovery_voucher_api.py` - API tests

### Modified Files
- `apps/payroll/models/__init__.py` - Export models
- `apps/payroll/apps.py` - Register signals
- `apps/payroll/api/serializers/__init__.py` - Export serializers
- `apps/payroll/api/filtersets/__init__.py` - Export filterset
- `apps/payroll/api/views/__init__.py` - Export viewset
- `apps/payroll/urls.py` - Register endpoint
- `apps/payroll/admin.py` - Admin configuration

## Security Considerations

1. **Input Validation**
   - All inputs validated via serializers
   - SafeTextField for note field (XSS prevention)
   - Amount must be positive integer

2. **Authentication & Authorization**
   - All endpoints require authentication
   - RBAC permissions enforced

3. **Audit Trail**
   - All changes logged via audit system
   - Audit logs are append-only

4. **Data Integrity**
   - Foreign key constraints
   - Unique code constraint
   - Protected deletion (via employee FK)

## Performance Optimizations

1. **Database**
   - Indexed fields: period, employee, status, updated_at
   - Cached employee fields for search

2. **API**
   - Pagination (25 per page)
   - select_related for employee lookups
   - Efficient filtering via django-filter

3. **Code Generation**
   - Uses database aggregation for sequence
   - Handles concurrent creation

## Maintenance

### Common Tasks

**Reset voucher status:**
```python
from apps.payroll.models import RecoveryVoucher

# Reset all calculated vouchers for a period
RecoveryVoucher.objects.filter(
    month__year=2025,
    month__month=9,
    status=RecoveryVoucher.RecoveryVoucherStatus.CALCULATED
    ).update(status=RecoveryVoucher.RecoveryVoucherStatus.NOT_CALCULATED)
```

**Bulk create vouchers:**
```python
vouchers = [
    RecoveryVoucher(
        code="TEMP_",  # Will be auto-generated
        name=f"Back pay {i}",
        voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
        employee=employee,
        amount=1000000 + i * 100000,
        month=date(2025, 9, 1)
    )
    for i in range(10)
]
RecoveryVoucher.objects.bulk_create(vouchers)
```

## Troubleshooting

**Issue: Code not generated**
- Ensure signals are imported in apps.py
- Check that code starts with "TEMP_"

**Issue: Employee validation fails**
- Verify employee status is ACTIVE or ONBOARDING
- Check employee exists in database

**Issue: Period format error**
- Use MM/YYYY format (e.g., "09/2025")
- Month must be 1-12

## Future Enhancements

1. Batch import from Excel
2. Approval workflow
3. Email notifications
4. Period lockdown (prevent changes after payroll finalized)
5. Historical reports and analytics
6. Integration with accounting system
