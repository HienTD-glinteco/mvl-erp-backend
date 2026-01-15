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
- `test_new_payroll_calculations.py`: Updated sales staff and tax method tests
- `test_family_deduction_and_allowance.py`: Updated to use `tax_calculation_method` instead of `employee_type`
- `test_salary_config_serializers.py`: Added `minimum_flat_tax_threshold` to test data
- `test_salary_config_api.py`: Added `minimum_flat_tax_threshold` to test data

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
