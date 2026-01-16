# Leader KPI Assessment Implementation Summary

## Overview
Implemented a new field `is_for_leader` in the `EmployeeKPIAssessment` model to mark assessments created specifically for department leaders. These assessments are evaluated only by admins when setting department grades and are excluded from all regular employee views and statistics.

## Changes Made

### 1. Database Migration
**File:** `apps/payroll/migrations/0011_add_is_for_leader_field.py`
- Added `is_for_leader` BooleanField (default=False) to `EmployeeKPIAssessment`
- Added database index on `is_for_leader` for query performance

### 2. Model Updates

#### EmployeeKPIAssessment Model
**File:** `apps/payroll/models/employee_kpi_assessment.py`
- Added `is_for_leader` field with appropriate help text
- Added index for the new field in Meta.indexes

#### DepartmentKPIAssessment Model
**File:** `apps/payroll/models/department_kpi_assessment.py`
- Updated `update_grade_distribution()` method to exclude leader assessments (`is_for_leader=False`)

### 3. Generation Logic
**File:** `apps/payroll/utils/kpi_assessment.py`
- Updated `generate_department_assessments_for_period()` function
- When creating assessment for department leader, set `is_for_leader=True`
- Leader assessment is created with:
  - `grade_hrm='C'` (default grade)
  - `finalized=True`
  - `is_for_leader=True`

### 4. View QuerySets Updates
All employee KPI assessment querysets now exclude leader assessments by adding `.filter(is_for_leader=False)`:

#### EmployeeKPIAssessmentViewSet
**File:** `apps/payroll/api/views/employee_kpi_assessment.py`
- Base queryset excludes leader assessments
- All filters and searches automatically exclude leader assessments

#### EmployeeSelfAssessmentViewSet
**File:** `apps/payroll/api/views/employee_kpi_assessment.py`
- `get_queryset()`: Excludes leader assessments
- `current_assessment()`: Excludes leader assessments
- Leaders cannot view their own leader assessment through self-assessment views

#### ManagerAssessmentViewSet
**File:** `apps/payroll/api/views/employee_kpi_assessment.py`
- `get_queryset()`: Excludes leader assessments
- `current_assessments()`: Excludes leader assessments
- Managers only see regular employee assessments, not leader assessments

#### Mobile API Views
**File:** `apps/payroll/api/views/mobile/kpi.py`
- Updated all three mobile viewsets to exclude leader assessments:
  - `EmployeeSelfAssessmentMobileViewSet`
  - `ManagerAssessmentMobileViewSet`
  - All related queries

### 5. Statistics and Period Management

#### KPIAssessmentPeriod Views
**File:** `apps/payroll/api/views/kpi_assessment_period.py`
- `finalize` action: Excludes leader assessments when setting default grades
- `summary` action: Excludes leader assessments from statistics

#### KPIAssessmentPeriod Serializer
**File:** `apps/payroll/api/serializers/kpi_assessment_period.py`
- `get_employee_count()`: Counts only non-leader assessments
- `get_employee_self_assessed_count()`: Counts only non-leader assessments
- `get_manager_assessed_count()`: Counts only non-leader assessments

#### Department Status Updates
**File:** `apps/payroll/utils/kpi_calculation.py`
- `update_department_assessment_status()`: Excludes leader assessments when calculating department statistics

#### Tasks
**File:** `apps/payroll/tasks.py`
- Updated `finalize` task to exclude leader assessments when processing

## Behavior

### Leader Assessment Creation
When a department KPI assessment is generated:
1. A `DepartmentKPIAssessment` is created with default grade "C"
2. An `EmployeeKPIAssessment` is created for the department leader with:
   - `is_for_leader=True`
   - `grade_hrm='C'`
   - `finalized=True`
   - Cannot be modified through regular employee/manager views

### Leader Assessment Updates
- Only admins can view/update leader assessments
- When department grade is updated, the leader's assessment `grade_hrm` is updated accordingly
- Leader assessments remain visible in admin interfaces

### Exclusions
Leader assessments are excluded from:
- Employee self-assessment views (web and mobile)
- Manager assessment views (web and mobile)
- Department statistics and grade distributions
- Period summary statistics
- All regular queryset filtering and search results

### Payroll Calculation
- Leader assessments are **NOT** excluded from payroll calculations
- Leaders receive salary based on their KPI grade like all other employees
- This ensures leaders are properly compensated based on department performance

## Testing
**File:** `apps/payroll/tests/test_kpi_leader_assessment.py`

Added comprehensive test coverage:
1. `test_generate_department_assessment_creates_leader_assessment`: Verifies leader assessment creation with correct flags
2. `test_leader_assessment_excluded_from_regular_queryset`: Tests exclusion from regular queries
3. `test_leader_assessment_excluded_from_statistics`: Verifies exclusion from department grade distribution
4. `test_leader_assessment_not_visible_in_employee_self_view`: Tests employee self-view exclusion
5. `test_leader_assessment_not_visible_in_manager_view`: Tests manager view exclusion
6. `test_department_grade_updates_leader_assessment`: Verifies department grade synchronization

All 177 KPI-related tests pass successfully.

## API Impact
No breaking changes to API responses. The field `is_for_leader` is added to the model but filtered out in all regular views, so existing API consumers won't see leader assessments in their responses.

## Migration Required
Yes - Run migration `0011_add_is_for_leader_field` to add the new field and index.

```bash
poetry run python manage.py migrate payroll
```

## Database Impact
- Adds one new BooleanField to `payroll_employee_kpi_assessment` table
- Adds one new database index
- Existing rows will have `is_for_leader=False` by default
- Existing leader assessments (if any) can be identified and updated manually if needed
