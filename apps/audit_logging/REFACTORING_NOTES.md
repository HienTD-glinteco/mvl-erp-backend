# Audit Logging Refactoring Notes

## Overview
This document describes the audit logging refactoring completed to simplify the system and improve performance.

## What Changed

### 1. Removed Automatic Related Object Tracking
**Before:** The system automatically tracked changes to:
- ManyToMany relationships
- Reverse ForeignKey relationships (inline objects)
- Recursively inspected related objects for field changes

**After:** The system only logs direct field changes on the object itself.

**Impact:** 
- Better performance (no expensive M2M queries or recursive inspection)
- Clearer audit logs (only direct changes, not cascading effects)
- More predictable behavior

### 2. Added `audit_log_target` Attribute
**Purpose:** Allow dependent/related models to declare where their changes should be logged.

**Usage:**
```python
@audit_logging_register
class EmployeeDependent(models.Model):
    audit_log_target = 'hrm.Employee'  # or Employee class reference
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    # ...
```

**Benefits:**
- All changes to a dependent model are logged under its parent/target
- Provides complete audit trail for the parent object
- Includes source metadata (source_model, source_pk, source_repr)
- Works seamlessly with the existing audit logging system

### 3. Cascade Delete Handling
**Feature:** Prevents duplicate logs when deleting a main object that cascade deletes dependents.

**How it works:**
- When deleting a main object, dependent objects with matching `audit_log_target` are marked
- These marked objects skip logging their own delete
- Only the main object delete is logged

**Example:**
```python
# Delete employee (has many dependents)
employee.delete()

# Result: Only ONE log entry (for employee delete)
# NOT: Multiple logs (employee + each dependent)
```

### 4. Pre-Delete State Capture
**Feature:** Captures object state before deletion for transaction safety.

**Purpose:** Ensures we have complete object data even if delete is rolled back.

## Migration Guide

### For M2M Changes
**Before (automatic):**
```python
article.tags.add(tag1, tag2)
# M2M changes were automatically logged
```

**After (explicit):**
```python
article.tags.add(tag1, tag2)
log_audit_event(
    action=LogAction.CHANGE,
    modified_object=article,
    user=request.user,
    request=request,
    change_message=f"Added tags: {tag1}, {tag2}",
)
```

### For Dependent Models
**Before:**
```python
@audit_logging_register
class EmployeeDependent(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    # Changes logged as separate EmployeeDependent entries
```

**After:**
```python
@audit_logging_register
class EmployeeDependent(models.Model):
    audit_log_target = 'hrm.Employee'
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    # Changes now logged under Employee with source metadata
```

## Which Models Should Use audit_log_target?

Use `audit_log_target` for models that are:
1. **Owned by** another model (e.g., OrderLineItem owned by Order)
2. **Part of** another model (e.g., EmployeeDependent part of Employee)
3. **Inline details** of another model (e.g., ContactAddress for Contact)

Do NOT use for:
1. Independent models (e.g., User, Customer, Product)
2. Many-to-Many join tables (handle explicitly in business logic)
3. Models that have their own lifecycle separate from others

## Examples in Codebase

### EmployeeDependent
```python
@audit_logging_register
class EmployeeDependent(BaseModel):
    audit_log_target = "hrm.Employee"
    employee = models.ForeignKey("hrm.Employee", on_delete=models.PROTECT)
```

**Result:** When you add/update/delete a dependent:
- Log appears under Employee's audit trail
- Includes: source_model="employeedependent", source_pk, source_repr
- Change message: "Added/Modified/Deleted Employee Dependent: ..."

### EmployeeRelationship
```python
@audit_logging_register
class EmployeeRelationship(BaseModel):
    audit_log_target = "hrm.Employee"
    employee = models.ForeignKey("hrm.Employee", on_delete=models.PROTECT)
```

**Result:** Same pattern as EmployeeDependent.

## Testing

### New Tests
- `test_audit_log_target.py`: Comprehensive tests for the new functionality
- Updated `test_related_changes.py`: Reflects simplified behavior

### Test Coverage
- audit_log_target registration and resolution
- Dependent model create/update/delete logging
- Cascade delete prevention
- M2M no longer automatically tracked
- Direct field changes still logged

## Performance Improvements

### Before
- Expensive M2M queries to detect changes
- Recursive inspection of related objects
- Multiple database queries per save operation

### After
- No automatic M2M queries
- No recursive inspection
- Only direct field comparison
- Significantly faster for models with many relationships

## Best Practices

1. **Use audit_log_target for dependent models**
   ```python
   audit_log_target = 'app.MainModel'
   ```

2. **Log M2M changes explicitly**
   ```python
   obj.tags.add(tag)
   log_audit_event(action=LogAction.CHANGE, modified_object=obj, ...)
   ```

3. **Use string references for circular imports**
   ```python
   audit_log_target = 'hrm.Employee'  # String reference
   # Instead of: audit_log_target = Employee  # Direct reference
   ```

4. **Check audit trail in target model**
   ```python
   # GET /api/employees/{id}/histories/
   # Will show Employee changes AND dependent changes
   ```

## Backwards Compatibility

### What Still Works
- All existing audit logging for direct field changes
- ViewSet mixin (AuditLoggingMixin)
- log_audit_event function
- Batch context
- Manual logging

### What Changed
- `related_changes` field is no longer populated
- M2M changes not automatically logged
- Need to add `audit_log_target` for dependent models

### Migration Steps
1. Add `audit_log_target` to dependent models
2. Add explicit M2M logging where needed
3. Test audit trails for completeness
4. Update any code that relied on `related_changes` field

## Questions?

Refer to:
- `apps/audit_logging/README.md` - Complete documentation
- `apps/audit_logging/tests/test_audit_log_target.py` - Examples and tests
- `apps/hrm/models/employee_dependent.py` - Real implementation example
