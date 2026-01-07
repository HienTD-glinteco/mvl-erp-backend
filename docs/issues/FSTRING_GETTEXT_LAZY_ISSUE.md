# F-String with gettext_lazy Causes Unstable Translation Messages

**Created**: 2026-01-07  
**Priority**: Medium  
**Status**: Open  
**Affects**: `makemessages` / `pre-commit` / Translation workflow

---

## Problem Summary

Using f-strings inside `gettext_lazy` (`_()`) causes translation message IDs (msgid) to be unstable across different environments and runs. This results in:

- Translations being deleted and re-added in `.po` files
- Fuzzy markers appearing on previously translated strings
- Inconsistent `django.po` changes between team members' commits

---

## Root Cause

When you use an f-string inside `_()`:

```python
from django.utils.translation import gettext_lazy as _

help_text=_(
    f"Number of rows to process per batch (default: {DEFAULT_BATCH_SIZE}, range: {MIN_BATCH_SIZE}-{MAX_BATCH_SIZE})"
)
```

The f-string is **evaluated at import time**, not at translation time. This means:

1. The msgid becomes a **literal string** with the values substituted (e.g., `"... (default: 100, range: 1-1000)"`)
2. If constants have different values, load order differs, or cache states vary, the msgid changes
3. `makemessages` sees this as a "new" string and marks old translations as obsolete/fuzzy

---

## Affected Files

Current occurrences in the codebase:

| File | Line | Code |
|------|------|------|
| `apps/imports/api/serializers.py` | 34 | `_(f"Number of rows to process per batch...")` |
| `apps/imports/api/serializers.py` | 48 | `_(f"Number of header rows to skip...")` |
| `apps/hrm/api/serializers/holiday.py` | 72 | `_(f"Compensatory workday date overlaps...")` |
| `apps/hrm/api/serializers/holiday.py` | 236 | `_(f"Compensatory date {comp_date} must be...")` |
| `apps/hrm/api/serializers/holiday.py` | 266 | `_(f"Compensatory date {comp_date} falls within...")` |
| `apps/hrm/api/serializers/holiday.py` | 282 | `_(f"Compensatory date {comp_date} overlaps...")` |
| `apps/payroll/api/serializers/penalty_ticket.py` | 165 | `_(f"Tickets not found: {missing_ids}")` |
| `apps/payroll/api/views/kpi_assessment_period.py` | 394 | `_(f"Assessment period for {month_str} already exists")` |

---

## Solution

### Option 1: Use `.format()` with lazy string (Recommended for static values)

```python
# Before (WRONG)
help_text=_(
    f"Number of rows to process per batch (default: {DEFAULT_BATCH_SIZE})"
)

# After (CORRECT)
help_text=_(
    "Number of rows to process per batch (default: {DEFAULT_BATCH_SIZE})"
).format(DEFAULT_BATCH_SIZE=DEFAULT_BATCH_SIZE)
```

### Option 2: Use `%` formatting (Django's traditional approach)

```python
# Before (WRONG)
_(f"Compensatory date {comp_date} overlaps with holiday: {holiday_name}")

# After (CORRECT)
_("Compensatory date %(comp_date)s overlaps with holiday: %(holiday_name)s") % {
    "comp_date": comp_date,
    "holiday_name": holiday_name,
}
```

### Option 3: Keep variables in the msgid for translator context

If translators need to understand the placeholders, use named format placeholders:

```python
# msgid will be: "Processing {count} items..."
# Translators see the placeholder names and can reorder them
_(
    "Processing {count} items in {location}"
).format(count=item_count, location=location_name)
```

---

## Django Documentation Reference

From [Django Translation Documentation](https://docs.djangoproject.com/en/5.2/topics/i18n/translation/#standard-translation):

> Use `%s` or `%(name)s` style formatting, or `.format()` method **after** the `_()` call. Do not use f-strings inside `_()` as they are evaluated before translation extraction.

---

## Verification

After fixing, run:

```bash
# Clean regenerate messages
poetry run python manage.py makemessages -l vi --no-obsolete

# Check for unstable entries
git diff locale/vi/LC_MESSAGES/django.po
```

The diff should only show actual new/changed strings, not the same strings being removed and re-added.

---

## Prevention

Consider adding a linting rule or pre-commit check to detect `_(f"..."` patterns:

```bash
# Simple grep check
grep -rn '_\s*(f"' apps/ --include="*.py"
```
