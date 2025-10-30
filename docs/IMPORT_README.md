# XLSX Import Documentation

## Quick Links

- **[📘 Comprehensive Guide](IMPORT_XLSX_COMPREHENSIVE.md)** - Complete documentation with all features, examples, and best practices
- **[🚀 Quick Start](IMPORT_XLSX_COMPREHENSIVE.md#quick-start)** - Get started in 5 minutes
- **[⚙️ Configuration Format](IMPORT_XLSX_COMPREHENSIVE.md#configuration-format)** - JSON/YAML config reference
- **[💡 Examples](IMPORT_XLSX_COMPREHENSIVE.md#examples)** - Real-world usage examples
- **[🔧 Troubleshooting](IMPORT_XLSX_COMPREHENSIVE.md#troubleshooting)** - Common issues and solutions

## What's New (Latest Version)

### Config-Driven Multi-Model Import System 🎉

The import system has been completely refactored to support advanced, config-driven imports with JSON/YAML configuration.

**Key Features**:
- ✅ **Dual Mode**: Simple auto-schema OR advanced config-driven
- ✅ **Multi-Model Imports**: Import Employee, Account, WorkEvent from single sheet
- ✅ **Field Transformation**: Combine day/month/year into date
- ✅ **Create-If-Not-Found**: Auto-create Position, Department, Division, Branch
- ✅ **Multi-Level Hierarchies**: Department → Division → Branch
- ✅ **Conditional Relations**: Create WorkEvent only if Resignation Date exists
- ✅ **Async Processing**: Background import with Celery for large files
- ✅ **Preview Mode**: Validate without saving (dry-run)
- ✅ **Error Reports**: Download detailed XLSX error reports
- ✅ **Backward Compatible**: Existing simple imports still work

## Two Import Modes

### Simple Mode (Auto Schema)

Perfect for basic single-model imports:

```python
class ProjectViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
```

**Excel**:
```
| name      | start_date | budget    |
|-----------|------------|-----------|
| Project A | 2024-01-01 | 100000.00 |
```

### Advanced Mode (Config-Driven)

For complex multi-model imports:

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
                        "combine": ["Day", "Month", "Year"],
                        "format": "YYYY-MM-DD"
                    },
                    "department": {
                        "model": "Department",
                        "lookup": "Department",
                        "create_if_not_found": true,
                        "relations": {
                            "division": {
                                "model": "Division",
                                "lookup": "Division"
                            }
                        }
                    }
                },
                "relations": {
                    "accounts": [{
                        "model": "Account",
                        "fields": {
                            "bank": "VPBank",
                            "account_number": "VPBank Account"
                        }
                    }]
                }
            }]
        }
```

**Excel**:
```
| Employee Code | Name     | Day | Month | Year | Department  | Division   | VPBank Account |
|---------------|----------|-----|-------|------|-------------|------------|----------------|
| EMP001        | John Doe | 15  | 1     | 2024 | Engineering | Technology | 123456789      |
```

**Result**: Creates/updates Employee, creates Department (if not exists), creates Division (if not exists), creates Account

## API Usage

### Sync Import (Default)
```bash
POST /api/employees/import/
Content-Type: multipart/form-data
file: employees.xlsx
```

### Async Import (For Large Files)
```bash
POST /api/employees/import/?async=true
```

### Preview Mode (Dry-Run)
```bash
POST /api/employees/import/?preview=true
```

## Architecture

```
libs/import_xlsx/
├── import_mixin.py              # DRF ViewSet mixin
├── mapping_config.py            # Config parser & validator
├── field_transformer.py         # Field combination & transformation
├── relationship_resolver.py     # Create-if-not-found logic
├── multi_model_processor.py     # Multi-model import processor
├── tasks.py                     # Celery async tasks
├── utils.py                     # Shared utilities
├── serializers.py               # Response serializers
├── error_report.py              # Error XLSX generator
├── storage.py                   # File storage backend
└── import_constants.py          # Constants
```

## Configuration Example

Full configuration example showing all features:

```json
{
  "sheets": [{
    "name": "Employees",
    "model": "Employee",
    "app_label": "hrm",
    "fields": {
      "employee_code": "Employee Code",
      "name": "Name",
      "status": "Status",
      "start_date": {
        "combine": ["Start Day", "Start Month", "Start Year"],
        "format": "YYYY-MM-DD"
      },
      "position": {
        "model": "Position",
        "lookup": "Position",
        "create_if_not_found": true
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
          },
          "parent_department": {
            "model": "Department",
            "lookup": "Parent Department"
          }
        }
      }
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

## Environment Configuration

```bash
# .env
IMPORTER_CELERY_ENABLED=true
IMPORTER_STORAGE_BACKEND=local  # or 's3'
IMPORTER_LOCAL_STORAGE_PATH=imports
IMPORTER_MAX_PREVIEW_ROWS=10
```

## Response Examples

**Successful Import**:
```json
{
  "success_count": 95,
  "error_count": 0,
  "errors": [],
  "detail": "Import completed successfully"
}
```

**Import with Errors**:
```json
{
  "success_count": 90,
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

**Async Import Response**:
```json
{
  "task_id": "abc-123",
  "status": "PENDING",
  "message": "Import task has been queued"
}
```

**Preview Mode Response**:
```json
{
  "valid_count": 95,
  "invalid_count": 5,
  "errors": [...],
  "preview_data": [...],
  "detail": "Preview completed"
}
```

## Migration Guide

### From Simple to Advanced Mode

**Before**:
```python
class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
```

**After**:
```python
class EmployeeViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    def get_import_config(self, request, file):
        return {...}  # Your config here
```

**Note**: Both modes work simultaneously. Simple mode is used when only `get_import_schema()` is defined. Advanced mode is used when `get_import_config()` is defined.

## Documentation Files

- **IMPORT_XLSX_COMPREHENSIVE.md** - Complete guide with all features
- **IMPORT_FEATURE_SUMMARY.md** - High-level implementation overview
- **IMPORT_NEW_FEATURES.md** - Detailed feature descriptions
- **examples/role_import_example.md** - Practical examples

## Support

For questions, issues, or feature requests:
1. Check the [Comprehensive Guide](IMPORT_XLSX_COMPREHENSIVE.md)
2. Review [Examples](IMPORT_XLSX_COMPREHENSIVE.md#examples)
3. See [Troubleshooting](IMPORT_XLSX_COMPREHENSIVE.md#troubleshooting)
4. Contact the development team

---

**Last Updated**: 2024-01-13
**Version**: 2.0 (Config-Driven Multi-Model System)
