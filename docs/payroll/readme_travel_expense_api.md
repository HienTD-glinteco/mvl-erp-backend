# Travel Expense API (Payroll)

Base URL examples below assume:

- API base: `https://api.mvl.glinteco.com`
- Auth: Bearer token

## List travel expenses

```bash
curl -X GET "https://api.mvl.glinteco.com/api/payroll/travel-expenses/?search=client&expense_type=TAXABLE&ordering=-created_at" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Accept: application/json"
```

## Retrieve travel expense

```bash
curl -X GET "https://api.mvl.glinteco.com/api/payroll/travel-expenses/1/" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Accept: application/json"
```

## Create travel expense

```bash
curl -X POST "https://api.mvl.glinteco.com/api/payroll/travel-expenses/" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Client visit 11/2025",
    "expense_type": "TAXABLE",
    "employee_id": 101,
    "amount": 2500000,
    "month": "11/2025",
    "note": "Taxi + meals"
  }'
```

## Update travel expense (PUT)

```bash
curl -X PUT "https://api.mvl.glinteco.com/api/payroll/travel-expenses/1/" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Client visit updated",
    "expense_type": "TAXABLE",
    "employee_id": 101,
    "amount": 3000000,
    "month": "11/2025",
    "note": "Updated: Taxi + meals + hotel"
  }'
```

## Partial update travel expense (PATCH)

```bash
curl -X PATCH "https://api.mvl.glinteco.com/api/payroll/travel-expenses/1/" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 3500000
  }'
```

## Delete travel expense

```bash
curl -X DELETE "https://api.mvl.glinteco.com/api/payroll/travel-expenses/1/" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Export travel expenses (XLSX)

### Export as presigned link (default)

```bash
curl -X GET "https://api.mvl.glinteco.com/api/payroll/travel-expenses/export/?delivery=link&expense_type=TAXABLE&month=11/2025" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Accept: application/json"
```

### Export as direct file download

This returns an XLSX file response (not JSON).

```bash
curl -L -X GET "https://api.mvl.glinteco.com/api/payroll/travel-expenses/export/?delivery=direct" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -o travel-expenses.xlsx
```

### Export asynchronously (if enabled)

```bash
curl -X GET "https://api.mvl.glinteco.com/api/payroll/travel-expenses/export/?async=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Accept: application/json"
```
