# Config-Driven XLSX Import System - Comprehensive Guide

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Import Modes](#import-modes)
4. [Quick Start](#quick-start)
5. [Configuration Format](#configuration-format)
6. [Advanced Features](#advanced-features)
7. [API Reference](#api-reference)
8. [Examples](#examples)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The **ImportXLSXMixin** provides a powerful, config-driven import system for Django REST Framework ViewSets. It supports both simple single-model imports and advanced multi-model imports with complex relationships, field transformations, and conditional logic.

### Key Capabilities

- ✅ **Dual Mode**: Simple auto-schema OR advanced config-driven imports
- ✅ **Multi-Model Imports**: Import related models (Employee, Account, WorkEvent) from single sheet
- ✅ **Field Transformation**: Combine multiple columns (day/month/year → date)
- ✅ **Create-If-Not-Found**: Auto-create related objects (Position, Department, Division, Branch)
- ✅ **Multi-Level Hierarchies**: Handle nested relationships (Department → Division → Branch)
- ✅ **Conditional Relations**: Create objects based on conditions (WorkEvent if Resignation Date exists)
- ✅ **Async Processing**: Background import with Celery for large files (>1000 rows)
- ✅ **Preview Mode**: Validate data without saving (dry-run)
- ✅ **Error Reports**: Download detailed XLSX error reports
- ✅ **Audit Logging**: Automatic audit trail for all imported data
- ✅ **Backward Compatible**: Existing simple imports continue to work

---

## Architecture

### Component Overview

```
libs/import_xlsx/
├── import_mixin.py              # DRF ViewSet mixin (dual mode support)
├── mapping_config.py            # JSON/YAML config parser & validator
├── field_transformer.py         # Field combination & transformation
├── relationship_resolver.py     # Create-if-not-found, nested relations
├── multi_model_processor.py     # Multi-model import processor
├── tasks.py                     # Celery async tasks
├── utils.py                     # Shared utilities
├── serializers.py               # Response serializers
├── error_report.py              # Error XLSX generator
├── storage.py                   # File storage backend
└── import_constants.py          # Constants
```

### Import Flow

```
┌──────────────────┐
│  Upload XLSX     │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│ Detect Import Mode           │
│ (Simple or Advanced)         │
└────────┬─────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────────┐
│Simple  │ │Advanced (Config) │
│Schema  │ │Multi-Model       │
└───┬────┘ └────┬─────────────┘
    │           │
    └─────┬─────┘
          │
          ▼
┌──────────────────────┐
│ Parse XLSX           │
│ Map Headers          │
└─────────┬────────────┘
          │
          ▼
┌──────────────────────┐
│ Transform Fields     │
│ (Combine, Format)    │
└─────────┬────────────┘
          │
          ▼
┌──────────────────────┐
│ Resolve Relationships│
│ (Create if not found)│
└─────────┬────────────┘
          │
          ▼
┌──────────────────────┐
│ Validate Data        │
│ (Per Row)            │
└─────────┬────────────┘
          │
          ▼
┌──────────────────────┐
│ Import to Database   │
│ (Transaction per row)│
└─────────┬────────────┘
          │
          ▼
┌──────────────────────┐
│ Generate Error Report│
│ (If errors exist)    │
└──────────────────────┘
```

---

## Import Modes

### Simple Mode (Auto Schema)

**Best for**: Single model imports with basic field mapping

**Features**:
- Automatic field detection from model
- Basic ForeignKey/ManyToMany resolution
- No configuration required

**Usage**:
```python
class ProjectViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
```

### Advanced Mode (Config-Driven)

**Best for**: Complex imports with multiple models and relationships

**Features**:
- Multi-model imports from single sheet
- Field combination and transformation
- Create-if-not-found for related objects
- Multi-level hierarchies
- Conditional relations
- Cross-model dependency management

**Usage**:
```python
class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    
    def get_import_config(self, request, file):
        return {
            "sheets": [{
                "name": "Employees",
                "model": "Employee",
                "app_label": "hrm",
                "fields": {
                    "employee_code": "Employee Code",
                    "name": "Name",
                    "start_date": {
                        "combine": ["Start Day", "Start Month", "Start Year"],
                        "format": "YYYY-MM-DD"
                    }
                }
            }]
        }
```

---

## Quick Start

### 1. Simple Single-Model Import

```python
from libs import BaseModelViewSet, ImportXLSXMixin

class ProjectViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    module = "Projects"
    submodule = "Project Management"
    permission_prefix = "project"
```

**Excel Format**:
```
| name        | start_date | budget    |
|-------------|------------|-----------|
| Project A   | 2024-01-01 | 100000.00 |
| Project B   | 2024-02-01 | 50000.00  |
```

**API Call**:
```bash
POST /api/projects/import/
Content-Type: multipart/form-data

file: projects.xlsx
```

### 2. Advanced Multi-Model Import

```python
class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    
    def get_import_config(self, request, file):
        return {
            "sheets": [{
                "name": "Employees",
                "model": "Employee",
                "app_label": "hrm",
                "fields": {
                    "employee_code": "Employee Code",
                    "name": "Name",
                    "department": {
                        "model": "Department",
                        "lookup": "Department",
                        "create_if_not_found": true
                    }
                },
                "relations": {
                    "accounts": [{
                        "model": "Account",
                        "fields": {
                            "bank": "VPBank",
                            "account_number": "VPBank Account Number"
                        },
                        "create_if_not_found": true
                    }]
                }
            }]
        }
```

**Excel Format**:
```
| Employee Code | Name      | Department  | VPBank | VPBank Account Number |
|---------------|-----------|-------------|--------|-----------------------|
| EMP001        | John Doe  | Engineering | VPBank | 123456789             |
| EMP002        | Jane Smith| Marketing   | VPBank | 987654321             |
```

---

## Configuration Format

### Basic Structure

```json
{
  "sheets": [
    {
      "name": "SheetName",
      "model": "ModelName",
      "app_label": "app_name",
      "fields": {
        "field_name": "Excel Column Name"
      },
      "relations": {
        "related_field": [...]
      }
    }
  ]
}
```

### Field Types

#### 1. Simple Field Mapping

```json
{
  "fields": {
    "employee_code": "Employee Code",
    "name": "Name",
    "email": "Email"
  }
}
```

#### 2. Field Combination

Combine multiple Excel columns into one field:

```json
{
  "fields": {
    "start_date": {
      "combine": ["Start Day", "Start Month", "Start Year"],
      "format": "YYYY-MM-DD"
    },
    "birth_date": {
      "combine": ["Birth Day", "Birth Month", "Birth Year"],
      "format": "DD/MM/YYYY"
    }
  }
}
```

**Supported Date Formats**:
- `YYYY-MM-DD`
- `DD/MM/YYYY`
- `MM/DD/YYYY`
- `YYYY/MM/DD`

#### 3. ForeignKey Fields

**Basic ForeignKey with Defaults**:
```json
{
  "fields": {
    "position": {
      "model": "Position",
      "lookup": "Position Title",
      "create_if_not_found": true,
      "defaults": {
        "code": "AUTO"
      }
    }
  }
}
```

**ForeignKey with Field Mapping**:
```json
{
  "fields": {
    "department": {
      "model": "Department",
      "lookup": "Department Name",
      "fields": {
        "code": "Dept Code",
        "name": "Department Name",
        "description": "Dept Description"
      },
      "create_if_not_found": true
    }
  }
}
```

**Parameters**:
- `model`: Related model name
- `lookup`: Excel column name for lookup value
- `fields`: Map Excel columns to model fields (NEW - supports multiple field mapping)
- `create_if_not_found`: Create if not exists (default: false)
- `defaults`: Static default values when creating new object (merged with fields mapping)

#### 4. Nested ForeignKey (Multi-Level Hierarchy)

**Basic Nested Relations**:
```json
{
  "fields": {
    "department": {
      "model": "Department",
      "lookup": "Department Name",
      "create_if_not_found": true,
      "relations": {
        "division": {
          "model": "Division",
          "lookup": "Division Name",
          "create_if_not_found": true
        },
        "branch": {
          "model": "Branch",
          "lookup": "Branch Name",
          "create_if_not_found": true
        },
        "parent_department": {
          "model": "Department",
          "lookup": "Parent Department"
        }
      }
    }
  }
}
```

**Nested Relations with Field Mapping**:
```json
{
  "fields": {
    "department": {
      "model": "Department",
      "lookup": "Department Name",
      "fields": {
        "code": "Dept Code",
        "name": "Department Name"
      },
      "create_if_not_found": true,
      "relations": {
        "block": {
          "model": "Block",
          "lookup": "Block Name",
          "fields": {
            "code": "Block Code",
            "name": "Block Name"
          },
          "create_if_not_found": true,
          "relations": {
            "branch": {
              "model": "Branch",
              "lookup": "Branch Name",
              "fields": {
                "code": "Branch Code",
                "name": "Branch Name"
              },
              "create_if_not_found": true
            }
          }
        }
      }
    }
  }
}
```

This creates:
1. Branch with mapped fields (code, name) - if not exists
2. Block with Branch reference and mapped fields - if not exists  
3. Parent Department (if specified)
4. Department with Block reference and mapped fields

**Excel Format Example**:
```
| Dept Code | Department Name | Block Code | Block Name | Branch Code | Branch Name |
|-----------|-----------------|------------|------------|-------------|-------------|
| D001      | Engineering     | B001       | Tech Block | BR001       | HQ          |
| D002      | Marketing       | B002       | Biz Block  | BR002       | Branch A    |
```

### Relations Configuration

#### 1. One-to-Many Relations

```json
{
  "relations": {
    "accounts": [
      {
        "model": "Account",
        "fields": {
          "bank": "VPBank",
          "account_number": "VPBank Account Number"
        },
        "create_if_not_found": true
      },
      {
        "model": "Account",
        "fields": {
          "bank": "Vietcombank",
          "account_number": "VCB Account Number"
        },
        "create_if_not_found": true
      }
    ]
  }
}
```

#### 2. Conditional Relations

Create related objects only if certain conditions are met:

```json
{
  "relations": {
    "work_events": [
      {
        "model": "WorkEvent",
        "fields": {
          "type": "Resignation",
          "event_date": "Resignation Date"
        },
        "condition": {
          "field": "Resignation Date",
          "exists": true
        },
        "create_if_not_found": true
      }
    ]
  }
}
```

**Condition Types**:
- `exists`: true/false - Check if field has value

---

## Advanced Features

### 1. Async Import (Celery)

For large files (>1000 rows), use async processing:

**Configuration**:
```bash
# .env
IMPORTER_CELERY_ENABLED=true
IMPORTER_STORAGE_BACKEND=local  # or 's3'
```

**API Call**:
```bash
POST /api/employees/import/?async=true

Response (202 Accepted):
{
  "task_id": "abc-123-def-456",
  "status": "PENDING",
  "message": "Import task has been queued for processing"
}
```

**Check Status**:
```bash
GET /api/celery/task/abc-123-def-456/

Response:
{
  "status": "SUCCESS",
  "result": {
    "success_count": 950,
    "error_count": 50,
    "error_file_url": "https://s3.../errors.xlsx"
  }
}
```

### 2. Preview Mode (Dry-Run)

Validate data without saving to database:

```bash
POST /api/employees/import/?preview=true

Response:
{
  "valid_count": 95,
  "invalid_count": 5,
  "errors": [
    {
      "row": 5,
      "errors": {
        "email": ["Enter a valid email address."]
      }
    }
  ],
  "preview_data": [
    {
      "employee_code": "EMP001",
      "name": "John Doe",
      "email": "john@example.com"
    }
  ]
}
```

### 3. Error Reports

When import completes with errors, automatically generates downloadable XLSX error report:

```json
{
  "success_count": 95,
  "error_count": 5,
  "errors": [
    {"row": 3, "errors": {"email": ["Invalid email"]}},
    {"row": 7, "errors": {"department": ["Not found"]}}
  ],
  "error_file_url": "https://s3.amazonaws.com/.../import_errors_20240113.xlsx"
}
```

**Error Report Contains**:
- **Error Summary Sheet**: Row number, field name, error message
- **Original Data Sheet**: All data with error highlights

### 4. Custom Validation

**Model-Level Validation (Default)**:
```python
# Uses model.full_clean()
# Allows importing ALL fields including read-only ones
```

**Serializer-Level Validation (Custom)**:
```python
class EmployeeImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["employee_code", "name", "email"]
        # No read-only restrictions

class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer  # Used for CRUD
    
    def get_import_serializer_class(self):
        return EmployeeImportSerializer  # Used for imports
```

### 5. Audit Logging

Automatically integrated when used with `AuditLoggingMixin`:

```python
from apps.audit_logging import AuditLoggingMixin

class EmployeeViewSet(AuditLoggingMixin, ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    # All imported instances automatically logged with action=IMPORT
```

### 6. Permission Registration

Import action automatically generates permission metadata:

```python
{
    "code": "employee.import_data",
    "name": "Import Data Employees",
    "description": "Import Data an Employee",
    "module": "HRM",
    "submodule": "Employee Management"
}
```

---

## API Reference

### Import Endpoint

**POST** `/api/<resource>/import/`

**Query Parameters**:
- `async` (boolean): Use async processing (default: false)
- `preview` (boolean): Dry-run mode, don't save data (default: false)

**Request**:
- Content-Type: `multipart/form-data`
- Body: `file` - Excel (.xlsx) file

**Response (Sync Import)**:
```json
{
  "success_count": 95,
  "error_count": 5,
  "errors": [
    {
      "row": 3,
      "errors": {
        "email": ["Enter a valid email address."]
      }
    }
  ],
  "error_file_url": "https://s3.../errors.xlsx",
  "detail": "Import completed successfully"
}
```

**Response (Async Import)**:
```json
{
  "task_id": "abc-123-def-456",
  "status": "PENDING",
  "message": "Import task has been queued for processing"
}
```

**Response (Preview Mode)**:
```json
{
  "valid_count": 95,
  "invalid_count": 5,
  "errors": [...],
  "preview_data": [...],
  "detail": "Preview completed successfully"
}
```

### ViewSet Methods

#### `get_import_schema(request, file)`

For simple mode imports. Returns schema dict.

```python
def get_import_schema(self, request, file):
    return {
        "fields": ["name", "email", "phone"],
        "required": ["name", "email"]
    }
```

#### `get_import_config(request, file)`

For advanced mode imports. Returns configuration dict.

```python
def get_import_config(self, request, file):
    return {
        "sheets": [{
            "name": "Employees",
            "model": "Employee",
            "app_label": "hrm",
            "fields": {...},
            "relations": {...}
        }]
    }
```

#### `get_import_serializer_class()`

Returns custom serializer for import validation.

```python
def get_import_serializer_class(self):
    return EmployeeImportSerializer
```

---

## Examples

### Example 1: Simple Role Import

```python
from libs import BaseModelViewSet, ImportXLSXMixin

class RoleViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    module = "Core"
    submodule = "Role Management"
    permission_prefix = "role"
```

**Excel**:
```
| code  | name      | description         |
|-------|-----------|---------------------|
| ADMIN | Admin     | Administrator role  |
| USER  | User      | Regular user role   |
```

### Example 2: Employee with Department Hierarchy

```python
class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    
    def get_import_config(self, request, file):
        return {
            "sheets": [{
                "name": "Employees",
                "model": "Employee",
                "app_label": "hrm",
                "fields": {
                    "employee_code": "Employee Code",
                    "name": "Name",
                    "start_date": {
                        "combine": ["Start Day", "Start Month", "Start Year"],
                        "format": "YYYY-MM-DD"
                    },
                    "department": {
                        "model": "Department",
                        "lookup": "Department",
                        "create_if_not_found": true,
                        "relations": {
                            "division": {
                                "model": "Division",
                                "lookup": "Division",
                                "create_if_not_found": true
                            },
                            "branch": {
                                "model": "Branch",
                                "lookup": "Branch",
                                "create_if_not_found": true
                            }
                        }
                    },
                    "position": {
                        "model": "Position",
                        "lookup": "Position",
                        "create_if_not_found": true
                    }
                }
            }]
        }
```

**Excel**:
```
| Employee Code | Name      | Start Day | Start Month | Start Year | Department  | Division   | Branch | Position           |
|---------------|-----------|-----------|-------------|------------|-------------|------------|--------|--------------------|
| EMP001        | John Doe  | 15        | 1           | 2024       | Engineering | Technology | HQ     | Software Engineer  |
| EMP002        | Jane Smith| 1         | 2           | 2024       | Marketing   | Business   | HQ     | Marketing Manager  |
```

### Example 3: Employee with Multiple Accounts and Work Events

```python
def get_import_config(self, request, file):
    return {
        "sheets": [{
            "name": "Employees",
            "model": "Employee",
            "app_label": "hrm",
            "fields": {
                "employee_code": "Employee Code",
                "name": "Name",
                "status": "Status"
            },
            "relations": {
                "accounts": [
                    {
                        "model": "Account",
                        "fields": {
                            "bank": "VPBank",
                            "account_number": "VPBank Account Number"
                        },
                        "create_if_not_found": true
                    },
                    {
                        "model": "Account",
                        "fields": {
                            "bank": "Vietcombank",
                            "account_number": "VCB Account Number"
                        },
                        "create_if_not_found": true
                    }
                ],
                "work_events": [
                    {
                        "model": "WorkEvent",
                        "fields": {
                            "type": "Resignation",
                            "event_date": "Resignation Date"
                        },
                        "condition": {
                            "field": "Resignation Date",
                            "exists": true
                        },
                        "create_if_not_found": true
                    }
                ]
            }
        }]
    }
```

**Excel**:
```
| Employee Code | Name      | Status | VPBank Account | VCB Account | Resignation Date |
|---------------|-----------|--------|----------------|-------------|------------------|
| EMP001        | John Doe  | Active | 123456789      | 987654321   |                  |
| EMP002        | Jane Smith| Left   | 111222333      | 444555666   | 2024-01-15       |
```

**Result**:
- EMP001: 2 accounts created, no work event
- EMP002: 2 accounts created, 1 resignation work event created

---

## Best Practices

### 1. Configuration Management

**Store configurations as constants or load from database**:

```python
# config/import_configs.py
EMPLOYEE_IMPORT_CONFIG = {
    "sheets": [{
        "name": "Employees",
        "model": "Employee",
        "app_label": "hrm",
        "fields": {...}
    }]
}

# views.py
from config.import_configs import EMPLOYEE_IMPORT_CONFIG

class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    def get_import_config(self, request, file):
        return EMPLOYEE_IMPORT_CONFIG
```

### 2. Validation Strategy

- **Use model-level validation** for data migration (allows read-only fields)
- **Use serializer-level validation** for user data entry (stricter validation)

### 3. Error Handling

- Always check error reports for failed imports
- Use preview mode to validate before committing
- Handle conditional relations to avoid unnecessary object creation

### 4. Performance

- Use async mode for files > 1000 rows
- Create indexes on lookup fields (name, code)
- Consider batch size for very large imports

### 5. Testing

```python
# Test configuration
def test_import_config_validation():
    config = {
        "sheets": [{
            "name": "Test",
            "model": "TestModel",
            "fields": {"name": "Name"}
        }]
    }
    parser = MappingConfigParser(config)
    parser.validate()
```

---

## Troubleshooting

### Issue: "Model not found"

**Cause**: Model name or app_label incorrect

**Solution**: 
```python
{
    "model": "Employee",
    "app_label": "hrm"  # Make sure this matches your app
}
```

### Issue: "Field combination failed"

**Cause**: Missing columns or incorrect date format

**Solution**:
- Ensure all combined fields exist in Excel
- Check date format matches configuration
- Supported formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY

### Issue: "Circular dependency in relationships"

**Cause**: Department references itself incorrectly

**Solution**:
- Ensure parent_department references existing departments
- Consider importing in multiple passes

### Issue: "Import too slow"

**Solution**:
- Use async mode: `?async=true`
- Enable Celery: `IMPORTER_CELERY_ENABLED=true`
- Reduce validation complexity

### Issue: "Related object not created"

**Cause**: `create_if_not_found` not set

**Solution**:
```python
{
    "model": "Department",
    "lookup": "Department Name",
    "create_if_not_found": true  # Add this
}
```

---

## Configuration Reference

### Environment Variables

```bash
# Enable async import processing
IMPORTER_CELERY_ENABLED=false

# Storage backend for error reports
IMPORTER_STORAGE_BACKEND=local  # or 's3'

# Local storage path for error reports
IMPORTER_LOCAL_STORAGE_PATH=imports

# Maximum rows to return in preview mode
IMPORTER_MAX_PREVIEW_ROWS=10

# S3 configuration (if using S3 storage)
IMPORTER_S3_BUCKET_NAME=my-bucket
IMPORTER_S3_SIGNED_URL_EXPIRE=3600
```

---

## Migration from Simple to Advanced Mode

**Before (Simple)**:
```python
class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
```

**After (Advanced)**:
```python
class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    
    def get_import_config(self, request, file):
        return {
            "sheets": [{
                "name": "Employees",
                "model": "Employee",
                "app_label": "hrm",
                "fields": {
                    "employee_code": "Employee Code",
                    "name": "Name"
                }
            }]
        }
```

**Note**: Both modes can coexist. Simple mode is used when only `get_import_schema()` is defined. Advanced mode is used when `get_import_config()` is defined.

---

## Summary

The config-driven XLSX import system provides:

✅ **Flexibility**: Simple auto-schema OR advanced config-driven
✅ **Power**: Multi-model imports with complex relationships
✅ **Safety**: Validation, preview mode, error reports
✅ **Performance**: Async processing for large files
✅ **Maintainability**: Config-driven, no hardcoded logic
✅ **Extensibility**: Easy to add new models via config

For questions or issues, refer to the troubleshooting section or contact the development team.
