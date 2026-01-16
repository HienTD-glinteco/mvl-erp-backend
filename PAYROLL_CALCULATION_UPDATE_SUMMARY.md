# Payroll Calculation Update Summary

## Overview
Updated the payroll calculation system to support flexible tax calculation methods and improved employee categorization based on contract and department settings.

## Changes Made

### 1. SalaryConfig Model
**File**: `apps/payroll/initial_data/default_salary_config.json`
- Added `minimum_flat_tax_threshold` field (default: 2000000) to `personal_income_tax` configuration
- This threshold determines when FLAT_10 tax method should apply

**File**: `apps/payroll/api/serializers/salary_config.py`
- Updated `PersonalIncomeTaxSerializer` to include `minimum_flat_tax_threshold` field with default value

### 2. PayrollSlip Model
**File**: `apps/payroll/models/payroll_slip.py`
- Added snapshot fields for contract-related calculations:
  - `tax_calculation_method`: CharField - snapshot from Contract.tax_calculation_method
  - `net_percentage`: IntegerField - snapshot from Contract.net_percentage
  - `has_social_insurance`: BooleanField - snapshot from Contract.has_social_insurance
  - `is_sale_employee`: BooleanField - True if Department.function == BUSINESS

**Migration**: `apps/payroll/migrations/0009_add_payroll_slip_snapshot_fields.py`

### 3. PayrollSlipCalculationService
**File**: `apps/payroll/services/payroll_calculation.py`

#### Updated Methods:

**`_cache_employee_data()`**:
- Now ALWAYS updates employee data on every calculation (removed employee_code check)
- Added logic to snapshot `is_sale_employee` based on `Department.function == BUSINESS`

**`_cache_contract_data(contract)`**:
- Added snapshot of contract fields: `tax_calculation_method`, `net_percentage`, `has_social_insurance`

**`_set_zero_salary_fields()`**:
- Resets snapshot fields when no contract exists

**`_calculate_kpi_bonus()`**:
- If `is_sale_employee == True`: `kpi_bonus = base_salary * kpi_percentage`
- If `is_sale_employee == False`: `kpi_bonus = kpi_salary * kpi_percentage`

**`_calculate_overtime_pay()`**:
- Unified `actual_working_days_income` calculation formula:
  ```python
  official_income = official_working_days * total_position_income
  probation_income = probation_working_days * total_position_income * 0.85  # if has_social_insurance == REDUCED
  probation_income = probation_working_days * total_position_income          # if has_social_insurance == FULL
  actual_working_days_income = (official_income + probation_income) / standard_working_days
  ```

**`_calculate_insurance_contributions()`**:
- Check `has_social_insurance` snapshot field first
- If `False`, set all insurance values to 0 and return early
- If `True`, calculate based on employee official status and date

**`_calculate_personal_income_tax()`**:
- Tax calculation now based on `tax_calculation_method` snapshot field:
  - **PROGRESSIVE**: Full progressive tax calculation with deductions and non-taxable allowances
  - **FLAT_10**: Flat 10% tax if `gross_income >= minimum_flat_tax_threshold`, else 0
  - **NONE**: Set all tax-related fields to 0

### 4. Test Updates

Updated tests to reflect new logic:
- `test_new_payroll_calculations.py`: Updated sales staff and tax method tests, added snapshot field assertions
- `test_family_deduction_and_allowance.py`: Updated to use `tax_calculation_method` instead of `employee_type`
- `test_salary_config_serializers.py`: Added `minimum_flat_tax_threshold` to test data
- `test_salary_config_api.py`: Added `minimum_flat_tax_threshold` to test data

### 5. API Serializers

Updated serializers to return new fields to client:
- `apps/payroll/api/serializers/payroll_slip.py`:
  - **PayrollSlipSerializer**: Added `tax_calculation_method`, `net_percentage`, `has_social_insurance`, `is_sale_employee` fields
  - **PayrollSlipExportSerializer**: Added same fields for XLSX export functionality

## Business Logic Changes

### Before:
1. Tax calculation was based on employee type (OFFICIAL vs PROBATION/INTERN)
2. KPI bonus always calculated on `base_salary`
3. Insurance calculation only based on employee type
4. `actual_working_days_income` had different formulas for sales vs non-sales staff

### After:
1. Tax calculation based on Contract's `tax_calculation_method` field
2. KPI bonus calculation depends on `is_sale_employee` flag
3. Insurance calculation first checks Contract's `has_social_insurance` flag
4. Unified `actual_working_days_income` formula for all employees
5. Employee data always refreshed on each calculation

## Migration Required

Run the migration to add new fields:
```bash
poetry run python manage.py migrate payroll
```

## Testing

All 714 payroll tests pass successfully:
```bash
ENVIRONMENT=test poetry run pytest apps/payroll/tests/ -k "not slow"
```

## API Impact

The `minimum_flat_tax_threshold` is now included in SalaryConfig API responses. The field has a default value for backward compatibility with existing configs.

## Notes

- The new snapshot fields ensure that payroll calculations remain consistent even if contract or department settings change after calculation
- The `is_sale_employee` flag is determined by the employee's department function at calculation time
- Tax method is now contract-driven rather than employee-type-driven, providing more flexibility

## 6. Excel Export Updates

**File**: `apps/payroll/api/views/salary_period.py`

Updated the `payrollslips_export` action to include all new snapshot fields in the XLSX export:

### New Columns Added
- **Column G**: is_sale_employee (True/False)
- **Column X**: net_percentage (0.85 or 1.0)
- **Column AK**: has_social_insurance (True/False)
- **Column AW**: tax_calculation_method (progressive/flat_10/none - translated)
- **Column BA**: minimum_flat_tax_threshold (from salary config)

### Formula Updates
All Excel formulas updated to use snapshot fields instead of employment_status:
- **Column Y** (Actual working days income): Now uses net_percentage (X) → `=(W*S+V*S*X)/T`
- **Column AD** (Hourly rate): Uses net_percentage (X) → `=IF(X=0.85,S*0.85/T/8,S/T/8)`
- **Column AL** (Insurance base): Uses has_social_insurance (AK) → `=IF(AK=TRUE,K,0)`
- **Column AZ** (Non-taxable allowance): Uses net_percentage → `=SUM(L:M)/T*(V*X+W)`
- **Column BB** (Taxable income): Conditional based on tax_calculation_method (AW)
  - progressive: `=IF(AJ-SUM(AR:AT)-AY-AI-AZ>0,AJ-SUM(AR:AT)-AY-AI-AZ,0)`
  - flat_10: `=AJ`
  - none: `=0`
- **Column BC** (Personal income tax): Conditional based on tax_calculation_method (AW)
  - progressive: Full progressive tax bracket formula
  - flat_10: `=IF(BB>=BA,BB*0.1,0)`
  - none: `=0`

### Helper Functions Added
- `_get_tax_method_display()`: Translates tax_calculation_method for Excel display
- `_get_tax_formulas()`: Generates conditional tax formulas based on tax method

### Export Structure
- Total columns: 67 (was 62, added 5 new)
- Column range: A-BG
- Two sheets: "Ready Slips" and "Not Ready Slips"
- All formulas maintain Excel compatibility
