# Employee & Department KPI Assessment System

This document describes the implementation of the KPI assessment system for monthly employee and department evaluations.

## Overview

The KPI assessment system provides:
- **Snapshot-based assessments**: Preserves historical data even when criteria change
- **Dual scoring**: Self-assessment and manager assessment
- **Grade calculation**: Automatic grade assignment with ambiguous handling
- **Unit control**: Quota-based grade distribution validation
- **Department auto-assignment**: Department-level grades can be auto-assigned to employees
- **Finalization**: Lock assessments after completion with audit trail

## Models

### EmployeeKPIAssessment
Stores monthly KPI assessments for individual employees.

**Key Fields:**
- `employee`: Foreign key to User
- `month`: First day of assessment month
- `target`: Employee role/target (sales/backoffice)
- `kpi_config_version`: Snapshot of KPI config version
- `total_manager_percent`: Calculated percentage score
- `grade_manager`: Final grade (A/B/C/D)
- `grade_manager_overridden`: Manual grade override
- `needs_manager_decision`: Flag for ambiguous grades
- `finalized`: Lock status

**Constraints:**
- Unique: `(employee, month)`

### EmployeeKPIItem
Stores snapshot of individual KPI criteria for assessments.

**Key Fields:**
- `assessment`: Foreign key to EmployeeKPIAssessment
- `criterion_id`: Original criterion (nullable if deleted)
- `criterion_name`, `evaluation_type`, `component_total_score`: Snapshots
- `self_percent`, `manager_percent`: Scoring percentages
- `component_score_self`, `component_score_manager`: Calculated scores

### DepartmentKPIAssessment
Stores monthly grade assignments for departments.

**Key Fields:**
- `department`: Foreign key to Department
- `month`: Assessment month
- `grade`: Department grade (A/B/C/D)
- `default_grade`: Auto-created default (C)
- `auto_assigned_to_employees`: Whether auto-assignment was performed
- `finalized`: Lock status

**Constraints:**
- Unique: `(department, month)`

### DepartmentAssignmentLog
Audit log for department grade assignment actions.

## Business Logic

### Score Calculation

**Component Score:**
```python
component_score = (component_total_score * achieved_percent) / 100
```

With rules mapping:
```python
# Find matching rule for actual_percent
rule = find_rule_for_percent(actual_percent, rules_snapshot)
achieved_percent = rule.achieved_percent
component_score = (component_total_score * achieved_percent) / 100
```

**Total Calculation:**
```python
total_possible_score = sum(item.component_total_score for all items)
total_manager_score = sum(item.component_score_manager for all items)
total_manager_percent = (total_manager_score / total_possible_score) * 100
```

### Grade Resolution

**Single Code:**
If threshold has only one possible code, assign directly.

**Ambiguous (Multiple Codes):**
Based on `ambiguous_assignment` policy:
- `manual`: Mark `needs_manager_decision=True`, suggest `default_code`
- `auto_prefer_default`: Use `default_code` if available
- `auto_prefer_highest`: Choose best grade (A > B > C > D)
- `auto_prefer_first`: Use first `possible_code`

**Override:**
If `grade_manager_overridden` is set, always use that grade.

### Unit Control Validation

Validates grade distribution against quotas:

```python
# For department with unit type 'A'
rules = unit_control['A']
max_pct_A = rules['max_pct_A']  # e.g., 0.20 (20%)
max_pct_B = rules['max_pct_B']  # e.g., 0.30 (30%)
max_pct_C = rules['max_pct_C']  # e.g., 0.50 (50%)
min_pct_D = rules['min_pct_D']  # e.g., None or 0.10 (10%)

# Calculate actual percentages
N = total_employees
actual_pct_A = count_A / N

# Validate
if actual_pct_A > max_pct_A:
    violations.append("Grade A exceeds maximum")
```

### Department Auto-Assignment

**Algorithm:**
1. Get all employee assessments for department and month
2. Separate overridden and non-overridden employees
3. Sort non-overridden by `total_manager_percent` DESC
4. Calculate quotas:
   ```python
   max_a = floor(max_pct_A * N)
   max_b = floor(max_pct_B * N)
   max_c = floor(max_pct_C * N)
   min_d = ceil(min_pct_D * N) if min_pct_D else 0
   ```
5. Assign grades:
   - Top `max_a` employees → 'A'
   - Next `max_b` employees → 'B'
   - Next `max_c` employees → 'C'
   - Remaining → 'D'
6. Ensure `min_d` is satisfied (convert lowest C to D if needed)
7. Don't overwrite `grade_manager_overridden` unless `force=true`

## API Endpoints

### Employee KPI Assessments

**List/Create:**
- `GET /api/payroll/kpi/assessments/` - List all assessments with filtering
- `POST /api/payroll/kpi/assessments/` - Create new assessment

**Retrieve/Update:**
- `GET /api/payroll/kpi/assessments/{id}/` - Get assessment with items
- `PATCH /api/payroll/kpi/assessments/{id}/` - Update grade override or note

**Actions:**
- `POST /api/payroll/kpi/assessments/generate/?month=YYYY-MM&target=sales` - Generate assessments
- `PATCH /api/payroll/kpi/assessments/{id}/items/{item_id}/` - Update item score
- `POST /api/payroll/kpi/assessments/{id}/resync/?mode=add_missing` - Resync with criteria
- `POST /api/payroll/kpi/assessments/{id}/finalize/?force=false` - Finalize assessment

**Filters:**
- `employee` - Employee ID
- `employee_username` - Employee username
- `month` - Exact date (YYYY-MM-DD)
- `month_year` - Year-month (YYYY-MM)
- `target` - Target group
- `grade_manager` - Grade
- `finalized` - Boolean
- `needs_manager_decision` - Boolean

### Department KPI Assessments

**List/Create:**
- `GET /api/payroll/kpi/departments/assessments/` - List department assessments
- `POST /api/payroll/kpi/departments/assessments/` - Create new department assessment

**Retrieve/Update:**
- `GET /api/payroll/kpi/departments/assessments/{id}/` - Get department assessment
- `PATCH /api/payroll/kpi/departments/assessments/{id}/` - Update grade or note

**Actions:**
- `POST /api/payroll/kpi/departments/assessments/generate/?month=YYYY-MM` - Generate department assessments
- `POST /api/payroll/kpi/departments/assessments/{id}/apply-to-employees/?mode=auto&force=false` - Auto-assign grades
- `POST /api/payroll/kpi/departments/assessments/{id}/finalize/?force=false` - Finalize
- `GET /api/payroll/kpi/departments/assessments/{id}/assignments/` - View assignment logs

**Filters:**
- `department` - Department ID
- `department_code` - Department code
- `month` - Exact date
- `month_year` - Year-month (YYYY-MM)
- `grade` - Grade
- `finalized` - Boolean
- `auto_assigned_to_employees` - Boolean

## Management Command

Generate assessments via command line:

```bash
# Generate for all targets
python manage.py generate_kpi_assessments --month 2025-12 --all

# Generate for specific target
python manage.py generate_kpi_assessments --month 2025-12 --target sales

# Generate for specific employees
python manage.py generate_kpi_assessments --month 2025-12 --target sales --employee-ids 1,2,3

# Generate for specific departments
python manage.py generate_kpi_assessments --month 2025-12 --department-ids 1,2,3
```

## Workflow Examples

### Monthly Assessment Generation

1. **Generate assessments** (typically on 1st of month):
   ```
   POST /api/payroll/kpi/assessments/generate/?month=2025-12&target=sales
   ```
   - Creates EmployeeKPIAssessment for all active employees
   - Creates snapshot of KPICriterion as EmployeeKPIItem
   - Creates DepartmentKPIAssessment with default grade 'C'

2. **Employee self-assessment**:
   ```
   PATCH /api/payroll/kpi/assessments/{id}/items/{item_id}/
   {
     "self_percent": 90.0
   }
   ```
   - Employee fills in self_percent for each item
   - System calculates component_score_self

3. **Manager assessment**:
   ```
   PATCH /api/payroll/kpi/assessments/{id}/items/{item_id}/
   {
     "manager_percent": 85.0
   }
   ```
   - Manager fills in manager_percent for each item
   - System calculates component_score_manager
   - System calculates total_manager_percent
   - System determines grade_manager (may set needs_manager_decision)

4. **Manager decision** (if ambiguous):
   ```
   PATCH /api/payroll/kpi/assessments/{id}/
   {
     "grade_manager_overridden": "B"
   }
   ```

5. **Finalize employee assessments**:
   ```
   POST /api/payroll/kpi/assessments/{id}/finalize/
   ```
   - Validates unit control
   - Locks assessment (finalized=true)

### Department Grade Assignment

1. **Set department grade**:
   ```
   PATCH /api/payroll/kpi/departments/assessments/{id}/
   {
     "grade": "A"
   }
   ```

2. **Auto-assign to employees**:
   ```
   POST /api/payroll/kpi/departments/assessments/{id}/apply-to-employees/?mode=auto
   ```
   - Ranks employees by total_manager_percent
   - Assigns grades based on quota
   - Respects existing overrides
   - Updates employee assessments
   - Logs action in DepartmentAssignmentLog

3. **Review assignments**:
   ```
   GET /api/payroll/kpi/departments/assessments/{id}/assignments/
   ```
   - View assignment history and details

### Resync After Criteria Changes

If KPICriterion is added after assessment creation:

```
POST /api/payroll/kpi/assessments/{id}/resync/?mode=add_missing
```
- Adds new criteria as items
- Doesn't affect existing items
- Only works for non-finalized assessments

To completely rebuild items from current criteria:

```
POST /api/payroll/kpi/assessments/{id}/resync/?mode=apply_current
```
- **WARNING**: Deletes all existing items and scores!
- Rebuilds from current active KPICriterion
- Only use if assessment was created incorrectly

## Snapshot Behavior

The system preserves historical data through snapshots:

**When criteria change:**
- Existing assessments are NOT affected
- EmployeeKPIItem stores snapshot values
- Original criterion reference (criterion_id) can be NULL if deleted
- Snapshot fields remain unchanged

**Example:**
1. Create assessment with criterion "Revenue Achievement" (70 points)
2. Modify criterion to "Updated Revenue" (80 points)
3. Assessment item still shows "Revenue Achievement" (70 points)

**Why?**
- Ensures historical accuracy
- Prevents retroactive changes to completed assessments
- Maintains audit trail

## Security & Permissions

**Employee:**
- Can view own assessments
- Can update self_percent for own items
- Cannot update manager_percent or grades

**Manager:**
- Can view assessments for managed employees
- Can update manager_percent for managed employees
- Can set grade_manager_overridden
- Can finalize assessments

**HR/Admin:**
- Full access to all assessments
- Can force finalize (bypass unit control)
- Can resync assessments
- Can force department auto-assignment
- Can edit finalized assessments (with audit)

## Testing

Run tests:
```bash
# All KPI assessment tests
ENVIRONMENT=test pytest apps/payroll/tests/test_employee_kpi_assessment.py -v

# Specific test
ENVIRONMENT=test pytest apps/payroll/tests/test_employee_kpi_assessment.py::EmployeeKPIAssessmentModelTest::test_snapshot_preserved_after_criterion_change -v
```

Test coverage:
- Model creation and constraints
- Snapshot preservation
- Score calculation
- Grade resolution with ambiguous handling
- Resync functionality
- Unit control validation
- Department auto-assignment

## Performance Considerations

**Large Datasets:**
- Use select_related/prefetch_related for queries
- Batch create with bulk_create for items
- Use transactions for consistency
- Index on (employee, month) and (department, month)

**Optimization:**
- Filter by month_year for fast month queries
- Use list serializer for lightweight listing
- Paginate assessment lists
- Cache KPIConfig for repeated access

## Future Enhancements

Potential improvements:
- [ ] Scheduled Celery tasks for automatic generation
- [ ] Email notifications for assessment deadlines
- [ ] Historical comparison views
- [ ] Dashboard with analytics
- [ ] Export to Excel/PDF
- [ ] Workflow states (draft, submitted, reviewed, finalized)
- [ ] Comments/feedback on individual items
- [ ] Multi-level approval workflow
