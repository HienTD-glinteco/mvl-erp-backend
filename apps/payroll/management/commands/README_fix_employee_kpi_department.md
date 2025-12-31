# Fix Employee KPI Department Command

## Overview
This management command fixes the `department` field in `EmployeeKPIAssessment` records that have `NULL` values. This is needed after adding the department snapshot feature to preserve historical department data.

## Command
```bash
python manage.py fix_employee_kpi_department
```

## Options

### `--dry-run`
Preview changes without saving them to the database.

```bash
python manage.py fix_employee_kpi_department --dry-run
```

**Example output:**
```
Found 5 employee KPI assessments with NULL department
DRY RUN MODE - No changes will be saved
✓ Assessment ID 3: Employee MV000005387 (2025-12) → Phòng Kinh Doanh 98_BG
✓ Assessment ID 2: Employee MV00001 (2025-12) → Phòng Kinh Doanh 98_BG
...
DRY RUN - No changes were saved
Run without --dry-run to apply changes
```

### `--period PERIOD_ID`
Only fix records for a specific KPI assessment period.

```bash
python manage.py fix_employee_kpi_department --period=123
```

### `--employee EMPLOYEE_ID`
Only fix records for a specific employee.

```bash
python manage.py fix_employee_kpi_department --employee=456
```

### `--batch-size SIZE`
Number of records to process per batch (default: 500).

```bash
python manage.py fix_employee_kpi_department --batch-size=100
```

## Usage Examples

### 1. Preview all changes (recommended first step)
```bash
python manage.py fix_employee_kpi_department --dry-run
```

### 2. Fix all records
```bash
python manage.py fix_employee_kpi_department
```

### 3. Fix records for specific period
```bash
# Find period ID first
python manage.py shell -c "from apps.payroll.models import KPIAssessmentPeriod; print([(p.id, p.month) for p in KPIAssessmentPeriod.objects.all()])"

# Fix for that period
python manage.py fix_employee_kpi_department --period=3
```

### 4. Fix with smaller batches for large datasets
```bash
python manage.py fix_employee_kpi_department --batch-size=100
```

## What It Does

1. **Finds records**: Queries all `EmployeeKPIAssessment` records where `department` is `NULL`
2. **Sets department**: Uses the employee's **current** department to populate the field
3. **Handles edge cases**:
   - Skips records where employee has no department
   - Reports orphaned records (assessment without employee)
4. **Batch processing**: Processes records in batches for performance
5. **Transaction safety**: Each batch is wrapped in a transaction

## Important Notes

### ⚠️ Historical Accuracy Warning
This command uses the employee's **current** department. If employees have changed departments since the KPI assessment was created, this may not be historically accurate.

**If historical accuracy is critical:**
- Review the dry-run output carefully
- Consider manual review for employees who have changed departments
- Check employee department change history if available

### After Running
After fixing department fields, you should update grade distributions:

```bash
python manage.py populate_grade_distribution
```

This ensures department grade distributions reflect the corrected data.

## Verification

### Check if fix is needed
```bash
python manage.py shell -c "from apps.payroll.models import EmployeeKPIAssessment; print(f'Records needing fix: {EmployeeKPIAssessment.objects.filter(department__isnull=True).count()}')"
```

### After running, verify all fixed
```bash
python manage.py shell -c "from apps.payroll.models import EmployeeKPIAssessment; null_count = EmployeeKPIAssessment.objects.filter(department__isnull=True).count(); print(f'✓ Success!' if null_count == 0 else f'Still {null_count} records with NULL department')"
```

## Rollback
If you need to rollback (development only), you can set departments back to NULL:

```bash
python manage.py shell
>>> from apps.payroll.models import EmployeeKPIAssessment
>>> EmployeeKPIAssessment.objects.all().update(department=None)
```

**⚠️ Don't do this in production!**

## Troubleshooting

### "No module named 'apps.payroll.management'"
Make sure you're in the project root directory and Django can find the app.

### Command doesn't find records
Records may already be fixed. Run with `--dry-run` to check.

### "Transaction aborted"
May indicate database constraint issues. Check error output and fix manually if needed.

## Technical Details

- **Source**: `apps/payroll/management/commands/fix_employee_kpi_department.py`
- **Tests**: `apps/payroll/tests/test_fix_employee_kpi_department_command.py`
- **Related Migration**: `0022_remove_department_assignment_source_add_department.py`
- **Default batch size**: 500 records
- **Transaction**: Each batch is atomic
