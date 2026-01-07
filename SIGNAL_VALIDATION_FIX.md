# Signal Validation Error Handling Fix

## Problem

When `ValidationError` was raised in Django signals (like in `apps/payroll/signals/deadline_validation.py`), the API returned:
- **500 Internal Server Error** instead of **400 Bad Request**
- **Non-JSON response** instead of proper JSON error format
- **Signal was called multiple times** on the same save operation (e.g., during KPI assessment updates)

This occurred because:
1. Django's `ValidationError` (from `django.core.exceptions`) was not being properly converted to DRF's `ValidationError` format
2. Signals were triggered multiple times when models were saved during recalculation operations

## Root Cause

### Issue 1: Exception Handling
Django signals raise `django.core.exceptions.ValidationError`, which is different from `rest_framework.exceptions.ValidationError`. The DRF exception handler needs to explicitly convert Django ValidationErrors to DRF ValidationErrors for proper JSON formatting.

### Issue 2: Multiple Signal Calls
When PATCH `/api/kpi-assessments/manager/3/` was called:
1. First save: `serializer.save()` triggers `pre_save` signal
2. Second save: `recalculate_assessment_scores()` calls `assessment.save()` again, triggering `pre_save` signal again

This caused the deadline validation to run twice, and potentially fetch stale data from the database.

## Solution

### 1. Updated Custom Exception Handler

Modified `libs/drf/custom_exception_handler.py` to convert Django ValidationError to DRF ValidationError:

```python
def exception_handler(exc, context):
    # Convert Django ValidationError to DRF ValidationError for proper handling
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "error_dict"):
            exc = DRFValidationError(detail=exc.message_dict)
        elif hasattr(exc, "error_list"):
            exc = DRFValidationError(detail=exc.messages)
        else:
            exc = DRFValidationError(detail={"non_field_errors": exc.messages if hasattr(exc, "messages") else [str(exc)]})

    # Continue with standard DRF error handling
    response = drf_exception_handler(exc, context)
    ...
```

### 2. Optimized Signal to Run Only Once

Updated `apps/payroll/signals/deadline_validation.py`:

**For KPI Assessment Deadline:**
- Check `update_fields` parameter - if provided and doesn't include `manager_assessment_date`, skip validation
- Only validate when `manager_assessment_date` is actually changing (first-time submission)
- Use `only()` queryset to fetch minimal fields for performance

**For Overtime Entry Deadline:**
- Added check to only validate on creation (`if instance.pk: return`)

**For Proposal Deadline:**
- Already optimized (only validates on creation)

### 3. Updated Recalculation Functions

Modified `apps/payroll/utils/kpi_assessment.py` to use `update_fields`:

```python
# In recalculate_assessment_scores()
assessment.save(
    update_fields=[
        "total_possible_score",
        "total_employee_score",
        "total_manager_score",
        "grade_manager",
    ]
)

# In resync_assessment_add_missing()
assessment.save(
    update_fields=[
        "total_possible_score",
        "total_manager_score",
        "grade_manager",
    ]
)
```

### 4. Added DRF Standardized Errors Configuration

Added configuration in `settings/base/drf.py`:

```python
DRF_STANDARDIZED_ERRORS = {
    "ENABLE_IN_DEBUG_FOR_UNHANDLED_EXCEPTIONS": True,
}
```

## Result

### API Error Response
Now when validation errors are raised in signals:

**Before:**
```
HTTP 500 Internal Server Error
Content-Type: text/html
<html>Internal Server Error</html>
```

**After:**
```json
HTTP 400 Bad Request
Content-Type: application/json

{
  "type": "validation_error",
  "errors": [
    {
      "code": "invalid",
      "detail": "Cannot create PAID_LEAVE proposal after salary period deadline (2024-01-15)",
      "attr": "non_field_errors"
    }
  ]
}
```

### Signal Performance
**Before:** Signal called 2x on PATCH `/api/kpi-assessments/manager/3/`
- 1st call: During `serializer.save()`
- 2nd call: During `recalculate_assessment_scores(assessment.save())`

**After:** Signal validation logic runs only 1x
- 1st call: Full validation runs
- 2nd call: Skipped via `update_fields` check

## Testing

Added comprehensive tests:
- `tests/libs/test_exception_handler.py` - Unit tests for exception handler conversion (4 tests)
- `tests/apps/payroll/test_signal_validation.py` - Integration tests for signal validation (3 tests)

All tests verify that:
1. Django ValidationError is converted to DRF ValidationError
2. Response status code is 400 (not 500)
3. Response is properly formatted JSON
4. Error messages are preserved
5. Signal validation is skipped on recalculation saves

## Affected Signals

This fix applies to all signals that raise ValidationError:
- `apps/payroll/signals/deadline_validation.py`:
  - `validate_proposal_salary_deadline` ✅ Already optimized (creation only)
  - `validate_overtime_entry_deadline` ✅ Optimized (creation only)
  - `validate_kpi_assessment_deadline` ✅ Optimized (update_fields check)

## Performance Improvement

- **Database queries reduced**: Using `only()` to fetch minimal fields instead of full instance
- **Signal calls reduced**: Skip validation on recalculation saves using `update_fields`
- **Response time improved**: Single validation check instead of double validation

## Migration Notes

No database migration required. This is a pure code change that improves error handling and performance without affecting data structure or business logic.
