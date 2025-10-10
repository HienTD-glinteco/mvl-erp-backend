# Geographic Data API Documentation

## Overview

This document provides API documentation for the Geographic Data subsystem, which manages administrative divisions in Vietnam including provinces/cities and their sub-units (districts, wards, communes, townships).

## Base URL

```
/api/core/
```

## Authentication

All API endpoints require authentication using JWT tokens in the Authorization header:

```
Authorization: Bearer <token>
```

## Response Format

All API responses follow the standard envelope format:

```json
{
  "success": true,
  "data": <actual_response_data>,
  "error": null
}
```

---

## Endpoints

### 1. Provinces (Tỉnh/Thành phố)

#### List Provinces
- **GET** `/api/core/provinces/`
- **Description**: Get list of all provinces and cities (no pagination)
- **Query Parameters**:
  - `enabled` (boolean): Filter by active status (true/false)
  - `level` (string): Filter by administrative level (`central_city` or `province`)
  - `search` (string): Search by name, code, or English name
  - `ordering` (string): Sort by field (e.g., `code`, `-name`, `created_at`)

**Example Request:**
```bash
GET /api/core/provinces/?enabled=true&level=central_city
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "code": "01",
      "name": "Thành phố Hà Nội",
      "english_name": "Hanoi",
      "level": "central_city",
      "level_display": "Central City",
      "decree": "Nghị quyết 15/2019/NQ-CP",
      "enabled": true,
      "created_at": "2025-01-10T10:00:00Z",
      "updated_at": "2025-01-10T10:00:00Z"
    },
    {
      "id": 2,
      "code": "48",
      "name": "Thành phố Đà Nẵng",
      "english_name": "Da Nang",
      "level": "central_city",
      "level_display": "Central City",
      "decree": "Nghị quyết 120/2019/NQ-CP",
      "enabled": true,
      "created_at": "2025-01-10T10:00:00Z",
      "updated_at": "2025-01-10T10:00:00Z"
    }
  ]
}
```

#### Get Province Details
- **GET** `/api/core/provinces/{id}/`
- **Description**: Get detailed information about a specific province

**Example Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "code": "01",
    "name": "Thành phố Hà Nội",
    "english_name": "Hanoi",
    "level": "central_city",
    "level_display": "Central City",
    "decree": "Nghị quyết 15/2019/NQ-CP",
    "enabled": true,
    "created_at": "2025-01-10T10:00:00Z",
    "updated_at": "2025-01-10T10:00:00Z"
  }
}
```

#### Province Level Choices
- `central_city`: Central City (Thành phố Trung ương)
- `province`: Province (Tỉnh)

---

### 2. Administrative Units (Quận/Huyện/Xã/Phường)

#### List Administrative Units
- **GET** `/api/core/administrative-units/`
- **Description**: Get paginated list of all administrative units
- **Query Parameters**:
  - `enabled` (boolean): Filter by active status (true/false)
  - `parent_province` (integer): Filter by parent province ID
  - `level` (string): Filter by administrative level (`district`, `ward`, `commune`, `township`)
  - `search` (string): Search by name or code
  - `ordering` (string): Sort by field (e.g., `code`, `-name`, `parent_province__code`)
  - `page` (integer): Page number for pagination
  - `page_size` (integer): Number of items per page (max: 100)

**Example Request:**
```bash
GET /api/core/administrative-units/?parent_province=1&enabled=true&level=district&page_size=20
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "count": 30,
    "next": "/api/core/administrative-units/?page=2&parent_province=1",
    "previous": null,
    "results": [
      {
        "id": 1,
        "code": "001",
        "name": "Quận Ba Đình",
        "parent_province": 1,
        "province_code": "01",
        "province_name": "Thành phố Hà Nội",
        "level": "district",
        "level_display": "District",
        "enabled": true,
        "created_at": "2025-01-10T10:00:00Z",
        "updated_at": "2025-01-10T10:00:00Z"
      },
      {
        "id": 2,
        "code": "002",
        "name": "Quận Hoàn Kiếm",
        "parent_province": 1,
        "province_code": "01",
        "province_name": "Thành phố Hà Nội",
        "level": "district",
        "level_display": "District",
        "enabled": true,
        "created_at": "2025-01-10T10:00:00Z",
        "updated_at": "2025-01-10T10:00:00Z"
      }
    ]
  }
}
```

#### Get Administrative Unit Details
- **GET** `/api/core/administrative-units/{id}/`
- **Description**: Get detailed information about a specific administrative unit

**Example Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "code": "001",
    "name": "Quận Ba Đình",
    "parent_province": 1,
    "province_code": "01",
    "province_name": "Thành phố Hà Nội",
    "level": "district",
    "level_display": "District",
    "enabled": true,
    "created_at": "2025-01-10T10:00:00Z",
    "updated_at": "2025-01-10T10:00:00Z"
  }
}
```

#### Administrative Unit Level Choices
- `district`: District (Quận/Huyện/Thành phố/Thị xã)
- `ward`: Ward (Phường)
- `commune`: Commune (Xã)
- `township`: Township (Thị trấn)

---

## Data Import Management Command

### Overview

The `import_administrative_data` management command allows importing Province and AdministrativeUnit data from CSV or Excel files.

### Usage

```bash
python manage.py import_administrative_data --type=<province|unit> --file=<path/to/file> [--dry-run]
```

### Parameters

- `--type`: Required. Type of data to import (`province` or `unit`)
- `--file`: Required. Path to the CSV or Excel file
- `--dry-run`: Optional. Run in dry-run mode without saving to database

### Import Logic

The command implements smart update logic:
1. If a record with the same code exists but has different data:
   - Mark the old record as disabled (`enabled = False`)
   - Create a new record with updated data
2. If a record with the same code has the same data:
   - No changes are made
3. If the code does not exist:
   - Create a new record

### CSV File Format

#### Province CSV Format

```csv
code,name,english_name,level,decree
01,Thành phố Hà Nội,Hanoi,Thành phố Trung ương,Nghị quyết 15/2019/NQ-CP
02,Tỉnh Hà Giang,Ha Giang,Tỉnh,Nghị định 24/2019/NĐ-CP
```

**Required Fields:**
- `code`: Province code (unique identifier)
- `name`: Province name in Vietnamese

**Optional Fields:**
- `english_name`: English name
- `level`: Administrative level (`Thành phố Trung ương` or `Tỉnh`)
- `decree`: Legal decree reference

#### Administrative Unit CSV Format

```csv
code,name,parent_province_code,level
001,Quận Ba Đình,01,Quận
002,Quận Hoàn Kiếm,01,Quận
00001,Phường Phúc Xá,01,Phường
```

**Required Fields:**
- `code`: Unit code (unique identifier)
- `name`: Unit name in Vietnamese
- `parent_province_code`: Code of the parent province

**Optional Fields:**
- `level`: Administrative level (`Quận`, `Huyện`, `Thành phố`, `Thị xã`, `Xã`, `Phường`, `Thị trấn`)

### Level Mappings

The command automatically maps Vietnamese level names to internal codes:

**Provinces:**
- `Thành phố Trung ương` → `central_city`
- `Tỉnh` → `province`

**Administrative Units:**
- `Quận`, `Huyện`, `Thành phố`, `Thị xã` → `district`
- `Xã` → `commune`
- `Phường` → `ward`
- `Thị trấn` → `township`

### Examples

#### Import Provinces

```bash
# Import from CSV
python manage.py import_administrative_data --type=province --file=provinces.csv

# Import from Excel
python manage.py import_administrative_data --type=province --file=provinces.xlsx

# Dry-run mode (no actual changes)
python manage.py import_administrative_data --type=province --file=provinces.csv --dry-run
```

#### Import Administrative Units

```bash
# Import from CSV
python manage.py import_administrative_data --type=unit --file=units.csv

# Import from Excel
python manage.py import_administrative_data --type=unit --file=units.xlsx
```

### Sample Output

```
Starting import of province data from provinces.csv
Loaded 3 rows from file
Created province: 01 - Thành phố Hà Nội
Created province: 02 - Tỉnh Hà Giang
Updated province: 48 - Thành phố Đà Nẵng
Province import summary: 2 created, 1 updated, 1 disabled
Import completed successfully
```

---

## Error Handling

### Common Error Codes

- `400 Bad Request`: Invalid filter parameters or search query
- `401 Unauthorized`: Missing or invalid authentication token
- `404 Not Found`: Province or administrative unit not found
- `500 Internal Server Error`: Server-side error

### Error Response Format

```json
{
  "success": false,
  "data": null,
  "error": "Error message description"
}
```

---

## Pagination

Administrative unit list endpoints support pagination with the following query parameters:
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 20, max: 100)

**Note:** Province list endpoint does **not** use pagination and returns all results at once.

---

## Filtering and Search

### Province Filtering
- Filter by `enabled` status
- Filter by `level` (administrative level)
- Search across `name`, `code`, and `english_name`

### Administrative Unit Filtering
- Filter by `enabled` status
- Filter by `parent_province` (province ID)
- Filter by `level` (administrative level)
- Search across `name` and `code`

### Ordering
Both endpoints support ordering by any field using the `ordering` parameter. Use `-` prefix for descending order:
- `ordering=code` - Sort by code ascending
- `ordering=-name` - Sort by name descending
- `ordering=parent_province__code,code` - Multiple field ordering

---

## Data Model

### Province Model

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Integer | Auto | Primary key |
| code | String(50) | Yes | Unique province code |
| name | String(200) | Yes | Province name |
| english_name | String(200) | No | English name |
| level | Choice | Yes | Administrative level |
| decree | String(100) | No | Legal decree reference |
| enabled | Boolean | Yes | Active status (default: true) |
| created_at | DateTime | Auto | Creation timestamp |
| updated_at | DateTime | Auto | Last update timestamp |

### AdministrativeUnit Model

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Integer | Auto | Primary key |
| code | String(50) | Yes | Unique unit code |
| name | String(200) | Yes | Unit name |
| parent_province | ForeignKey | Yes | Reference to Province |
| level | Choice | Yes | Administrative level |
| enabled | Boolean | Yes | Active status (default: true) |
| created_at | DateTime | Auto | Creation timestamp |
| updated_at | DateTime | Auto | Last update timestamp |

---

## Best Practices

1. **Use Filtering**: When working with administrative units, always filter by `parent_province` to reduce response size
2. **Cache Provinces**: Province data changes rarely, consider caching the full list on the client side
3. **Pagination**: Use appropriate `page_size` for administrative units based on your UI needs
4. **Enabled Filter**: In production, typically filter by `enabled=true` to show only active records
5. **Import Order**: Always import provinces before importing administrative units
6. **Dry-Run First**: When importing large datasets, use `--dry-run` first to validate data

---

## Integration Example

### Fetching All Active Provinces

```javascript
// JavaScript/TypeScript example
const response = await fetch('/api/core/provinces/?enabled=true', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const data = await response.json();
const provinces = data.data;
```

### Fetching Districts for a Province

```javascript
const provinceId = 1; // Hanoi
const response = await fetch(
  `/api/core/administrative-units/?parent_province=${provinceId}&level=district&enabled=true`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
const data = await response.json();
const districts = data.data.results;
```

### Fetching Wards for a District

To fetch wards, you need to search by name or code since the unit structure is flat (all units reference the province, not parent units):

```javascript
const response = await fetch(
  `/api/core/administrative-units/?search=Ba Đình&level=ward&enabled=true`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
```
