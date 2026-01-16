# Excel Export Update Required

## Overview
The `SalaryPeriodViewSet.payrollslips_export` action needs to be updated to include the new PayrollSlip snapshot fields according to the updated `salary_excel_columns.md` specification.

## Files Modified
1. ✅ `apps/payroll/salary_excel_columns.md` - Updated with new column specifications
2. ⚠️  `apps/payroll/api/views/salary_period.py` - PARTIALLY UPDATED (needs completion)

## Changes Completed
✅ Updated `headers` array to include new columns
✅ Updated `groups` array with correct spans
✅ Updated `field_names` array with new field names

## Changes Still Needed in `build_sheet_data()` function

### 1. Add New Data Fields (around line 956-980)
After line 968 (employment_status), add:
```python
# G: Is sale employee
"is_sale_employee": slip.is_sale_employee,
```

### 2. Update Working Days Section (around line 985-990)
After line 990 (official_working_days), add:
```python
# X: Net percentage (0.85 or 1)
"net_percentage": 0.85 if slip.net_percentage == 85 else 1.0,
```

### 3. Update Actual Working Days Income Formula (around line 992-994)
Replace the formula at line 992-994 with:
```python
# Y: Actual working days income = (W*S+V*S*X)/T
"actual_working_days_income": f"=(W{excel_row}*S{excel_row}+V{excel_row}*S{excel_row}*X{excel_row})/T{excel_row}",
```

### 4. Update Hourly Rate Formula (around line 998-1000)
Replace with:
```python
# AD: Hourly rate = IF(X=0.85,S*0.85/T/8,S/T/8)
"hourly_rate": f"=IF(X{excel_row}=0.85,S{excel_row}*0.85/T{excel_row}/8,S{excel_row}/T{excel_row}/8)",
```

### 5. Update Column References in Overtime Formulas (around line 1001-1012)
All column references need to shift by 3 (due to new columns G, X, AK):
- Old AH → New AJ
- Old AI → New AL
- Update all formulas accordingly

### 6. Add Insurance Fields (after gross_income around line 1012)
```python
# AJ: Gross income formula updated
"gross_income": f"=Y{excel_row}+AH{excel_row}+AI{excel_row}",
# AK: Has social insurance
"has_social_insurance": slip.has_social_insurance,
# AL: Insurance base = IF(AK=TRUE,K,0)
"social_insurance_base": f"=IF(AK{excel_row}=TRUE,K{excel_row},0)",
```

### 7. Update Employer/Employee Insurance Formulas (around line 1016-1025)
Change references from AI to AL:
```python
# Employer contributions (AM-AQ)
"employer_social_insurance": f"=AL{excel_row}*{employer_si_rate}",
"employer_health_insurance": f"=AL{excel_row}*{employer_hi_rate}",
...
# Employee deductions (AR-AU)
"employee_social_insurance": f"=AL{excel_row}*{employee_si_rate}",
...
```

### 8. Add Tax Fields (around line 1027-1040)
```python
# Tax information (AV-BC)
"tax_code": slip.tax_code or "",  # AV
# AW: Tax calculation method (translate)
from apps.hrm.models import ContractType
tax_method_display = ""
if slip.tax_calculation_method:
    tax_method_display = dict(ContractType.TaxCalculationMethod.choices).get(
        slip.tax_calculation_method, slip.tax_calculation_method
    )
"tax_calculation_method": str(tax_method_display),  # AW
"dependent_count": slip.dependent_count or 0,  # AX
# AY: Total deduction
"total_deduction": f"={personal_deduction}+AX{excel_row}*{dependent_deduction}",
# AZ: Non-taxable allowance = SUM(L:M)/T*(V*X+W)
"non_taxable_allowance": f"=SUM(L{excel_row}:M{excel_row})/T{excel_row}*(V{excel_row}*X{excel_row}+W{excel_row})",
# BA: Minimum flat tax threshold
"minimum_flat_tax_threshold": tax_config.get("minimum_flat_tax_threshold", 2000000),
```

### 9. Update Taxable Income Formula (around line 1035)
```python
# BB: Taxable income - conditional based on tax_calculation_method
# progressive: IF(AJ-SUM(AR:AT)-AY-AI-AZ>0,AJ-SUM(AR:AT)-AY-AI-AZ,0)
# flat_10: =AJ
# none: =0
tax_method = slip.tax_calculation_method or ""
if tax_method == "progressive":
    taxable_income_formula = f"=IF(AJ{excel_row}-SUM(AR{excel_row}:AT{excel_row})-AY{excel_row}-AI{excel_row}-AZ{excel_row}>0,AJ{excel_row}-SUM(AR{excel_row}:AT{excel_row})-AY{excel_row}-AI{excel_row}-AZ{excel_row},0)"
elif tax_method == "flat_10":
    taxable_income_formula = f"=AJ{excel_row}"
else:  # none or empty
    taxable_income_formula = "=0"
"taxable_income": taxable_income_formula,
```

### 10. Update Personal Income Tax Formula (around line 1038-1042)
```python
# BC: Personal income tax - conditional based on tax_calculation_method
if tax_method == "progressive":
    tax_formula = f"=IF(BB{excel_row}<=5000000,BB{excel_row}*0.05,IF(BB{excel_row}<=10000000,BB{excel_row}*0.1-250000,IF(BB{excel_row}<=18000000,BB{excel_row}*0.15-750000,IF(BB{excel_row}<=32000000,BB{excel_row}*0.2-1650000,IF(BB{excel_row}<=52000000,BB{excel_row}*0.25-3250000,IF(BB{excel_row}<=80000000,BB{excel_row}*0.3-5850000,BB{excel_row}*0.35-9850000))))))"
elif tax_method == "flat_10":
    tax_formula = f"=IF(BB{excel_row}>=BA{excel_row},BB{excel_row}*0.1,0)"
else:  # none or empty
    tax_formula = "=0"
"personal_income_tax": tax_formula,
```

### 11. Update Final Columns (around line 1042-1052)
```python
# Adjustments (BD-BE)
"back_pay_amount": slip.back_pay_amount or 0,  # BD
"recovery_amount": slip.recovery_amount or 0,  # BE
# BF: Net salary = ROUND(AJ-SUM(AR:AT)-AU+BD-BE-BC,0)
"net_salary": f"=ROUND(AJ{excel_row}-SUM(AR{excel_row}:AT{excel_row})-AU{excel_row}+BD{excel_row}-BE{excel_row}-BC{excel_row},0)",
# BG: Bank account
"bank_account": (
    slip.employee.default_bank_account.account_number
    if slip.employee and slip.employee.default_bank_account
    else ""
),
```

## Summary of Column Changes
- **G**: is_sale_employee (NEW)
- **X**: net_percentage (NEW - was not in export before)
- **AK**: has_social_insurance (NEW)
- **AW**: tax_calculation_method (NEW)
- **BA**: minimum_flat_tax_threshold (NEW)
- All columns after G shifted by appropriate offsets

## Testing Required
After implementing these changes:
1. Test export with different tax calculation methods (progressive, flat_10, none)
2. Test with employees who have/don't have social insurance
3. Test with sale vs non-sale employees
4. Verify all Excel formulas calculate correctly
5. Check both "Ready Slips" and "Not Ready Slips" sheets

## Notes
- The export now uses snapshot fields instead of employment_status for calculations
- Tax calculation is now based on tax_calculation_method field, not employee type
- Insurance calculation is based on has_social_insurance field
- All formulas have been updated to reflect the new column positions
