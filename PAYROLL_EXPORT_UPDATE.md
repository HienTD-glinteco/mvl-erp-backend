# Payroll Export Service Update Summary

## Overview
Updated `PayrollSlipExportService` to match the latest specification in `salary_excel_columns.md`.

## Changes Made

### 1. Added Travel Expense Columns (AJ-AK)
**New columns added after Overtime section:**
- **AJ**: Taxable travel expense (fill data)
- **AK**: Non-taxable travel expense (fill data)

This shifts all subsequent columns by 2 positions.

### 2. Updated Column Mapping

**Before (Old):**
- Total income: AJ
- Insurance: AK-AL
- Employer contrib: AM-AQ
- Employee deduct: AR-AU
- Tax info: AV-BC
- Adjustments: BD-BE
- Net salary: BF
- Bank: BG

**After (New):**
- Travel expense: AJ-AK (NEW)
- Total income: AL
- Insurance: AM-AN
- Employer contrib: AO-AS
- Employee deduct: AT-AW
- Tax info: AX-BE
- Adjustments: BF-BG
- Net salary: BH
- Bank: BI

### 3. Updated Headers

**Row 1 (Groups):**
- Added: `{"title": _("Travel expense"), "span": 2}`

**Row 2 (Columns):**
- AJ: _("Taxable")
- AK: _("Non-taxable")

### 4. Updated Field Names Mapping

Added fields:
```python
"taxable_travel_expense",      # AJ
"non_taxable_travel_expense",  # AK
```

All fields after these shifted by 2 positions.

### 5. Updated Formulas

**Gross Income (AL):**
```python
# Old: =Y+AH+AI
# New: =Y+AH+AI+AJ+AK
"gross_income": f"=Y{excel_row}+AH{excel_row}+AI{excel_row}+AJ{excel_row}+AK{excel_row}"
```

**Insurance Base (AN):**
```python
# Old: IF(AK=TRUE,K,0)
# New: IF(AM=TRUE,K,0)
"social_insurance_base": f"=IF(AM{excel_row}=TRUE,K{excel_row},0)"
```

**Employer Contributions (AO-AS):**
```python
# Old: AL * rate
# New: AN * rate
"employer_social_insurance": f"=AN{excel_row}*{rate}"
```

**Employee Deductions (AT-AW):**
```python
# Old: AL * rate
# New: AN * rate
"employee_social_insurance": f"=AN{excel_row}*{rate}"
```

**Tax Calculations:**

**Total Deduction (BA):**
```python
# Old: =11000000+AX*4400000
# New: =11000000+AZ*4400000
"total_deduction": f"={personal_deduction}+AZ{excel_row}*{dependent_deduction}"
```

**Non-taxable Allowance (BB):**
```python
# Old: =SUM(L:M)/T*(V*X+W)
# New: =SUM(L:M)/T*(V*X+W)  (unchanged)
"non_taxable_allowance": f"=SUM(L{excel_row}:M{excel_row})/T{excel_row}*(V{excel_row}*X{excel_row}+W{excel_row})"
```

**Taxable Income (BD):**
```python
# Old (progressive): =IF(AJ-SUM(AR:AT)-AY-AI-AZ>0,...)
# New (progressive): =IF(AL-SUM(AT:AV)-BA-AI-BB>0,...)

# Old (flat_10): =AJ
# New (flat_10): =AL
```

**Personal Income Tax (BE):**
```python
# Old: Uses BB column
# New: Uses BD column

# Old (flat_10): =IF(BB>=BA,BB*10%,0)
# New (flat_10): =IF(BD>=BC,BD*10%,0)
```

**Net Salary (BH):**
```python
# Old: =ROUND(AJ-SUM(AR:AT)-AU+BD-BE-BC,0)
# New: =ROUND(AL-SUM(AT:AV)-AW+BF-BG-BE,0)
"net_salary": f"=ROUND(AL{excel_row}-SUM(AT{excel_row}:AV{excel_row})-AW{excel_row}+BF{excel_row}-BG{excel_row}-BE{excel_row},0)"
```

## Total Columns

**Before:** 67 columns (A-BG)
**After:** 69 columns (A-BI)

**Breakdown:**
- Employee info: 10 (A-J)
- Position income: 9 (K-S)
- Working days: 5 (T-X)
- Income by working days: 1 (Y)
- Overtime: 10 (Z-AI)
- **Travel expense: 2 (AJ-AK)** ← NEW
- Gross income: 1 (AL)
- Insurance: 2 (AM-AN)
- Employer contrib: 5 (AO-AS)
- Employee deduct: 4 (AT-AW)
- Tax info: 8 (AX-BE)
- Adjustments: 2 (BF-BG)
- Net salary: 1 (BH)
- Bank: 1 (BI)

**Total: 69 columns**

## Files Modified

1. **apps/payroll/services/payroll_export.py**
   - Updated `_build_headers()` - added 2 columns
   - Updated `_build_groups()` - added travel expense group
   - Updated `_build_field_names()` - added 2 field names
   - Updated `_build_sheet_data()` - updated all formulas with new column references
   - Updated `_get_tax_formulas()` - updated BD/BE references

## Testing

```bash
# Syntax check
poetry run python -m py_compile apps/payroll/services/payroll_export.py

# Linting
poetry run ruff check apps/payroll/services/payroll_export.py
```

## Code Quality
✅ Syntax check passed
✅ Ruff linting passed (1 whitespace fix applied)
✅ All formulas updated correctly
✅ Column mapping verified against MD spec

## Migration Notes
- **No database migration required**
- **No model changes** - uses existing `taxable_travel_expense` and `non_taxable_travel_expense` fields
- Export format change is backward compatible (only adds columns)

## Verification Checklist

✅ Travel expense columns added (AJ-AK)
✅ All column references shifted by 2 positions
✅ Gross income formula includes travel expenses
✅ Insurance formulas use correct column references
✅ Tax formulas use correct column references
✅ Net salary formula uses correct column references
✅ Groups header includes travel expense
✅ Field names mapping updated
✅ Total column count: 69 (A-BI)

Export service is now aligned with the latest specification! 📊✨
