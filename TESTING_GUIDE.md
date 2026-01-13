# Quick Testing Guide for Payroll Bug Fixes

## Test Setup

First, ensure you have test data ready:
```bash
# Set environment
export ENVIRONMENT=test

# Or run with environment inline
ENVIRONMENT=test poetry run pytest ...
```

## Issue 1: Employee Resignation Not Affecting Payroll

### Steps to Test Manually:

1. **Create test employee**:
   - Go to Employees → Create new employee
   - Name: "Test Employee 1"
   - Department: Any department
   - Position: Any position
   - Status: ACTIVE

2. **Create contract**:
   - Go to Contracts → Create new contract
   - Employee: Test Employee 1
   - Contract Type: Official Contract
   - Base Salary: 10,000,000
   - Status: ACTIVE

3. **Create salary period**:
   - Go to Payroll → Salary Periods → Create
   - Month: Current month
   - Calculate payroll slips

4. **Verify initial state**:
   - Open payroll slip for Test Employee 1
   - Note the department name and position name

5. **Change employee data**:
   - Go to Employees → Edit Test Employee 1
   - Transfer to different department/position (use Transfer action)

6. **Recalculate payroll**:
   - Go back to payroll slip
   - Click "Recalculate"

7. **Expected Result**: ✅ Department and position names should NOT change in the payroll slip

---

## Issue 2: Contract Updates Employee Type

### Steps to Test Manually:

1. **Create employee with probation type**:
   - Go to Employees → Create
   - Employee Type: PROBATION (or leave empty)
   - Status: ACTIVE

2. **Create official contract**:
   - Go to Contracts → Create
   - Contract Type: Choose an "Official" type contract
   - Status: ACTIVE
   - Effective Date: Today

3. **Expected Result**: ✅ Employee type should automatically change to "OFFICIAL"

### Verify with API:
```bash
# Check employee type changed
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/hrm/employees/{employee_id}/
```

---

## Issue 3: Contract Appendix Triggers Recalculation

### Steps to Test Manually:

1. **Create employee with contract**:
   - Employee: Test Employee 2
   - Base Contract: Base Salary = 10,000,000
   - Effective Date: Start of month

2. **Create salary period and calculate**:
   - Month: Current month
   - Verify payroll slip shows base_salary = 10,000,000

3. **Create contract appendix**:
   - Go to Contracts → Create Appendix
   - Parent Contract: The contract created above
   - Base Salary: 15,000,000
   - Effective Date: 15th of current month
   - Status: ACTIVE

4. **Check payroll slip**:
   - Wait a few seconds for async task
   - Refresh payroll slip page

5. **Expected Result**: ✅ Base salary should update to 15,000,000

### Verify with Logs:
```bash
# Check Celery task logs
tail -f logs/celery.log | grep recalculate_payroll_slip_task
```

---

## Issue 4: Resigned Employee Contract Retrieval

### Steps to Test Manually:

1. **Create employee**:
   - Name: Test Employee 3
   - Status: ACTIVE
   - Start Date: 1st of current month

2. **Create contract**:
   - Base Salary: 8,000,000
   - Status: ACTIVE
   - Effective Date: 1st of current month

3. **Resign employee**:
   - Go to Employee → Actions → Resign
   - Resignation Date: 20th of current month
   - Note: Contract will become EXPIRED

4. **Create salary period for current month**:
   - The resigned employee should be included
   - Calculate payroll

5. **Check payroll slip**:
   - Open slip for Test Employee 3
   - Check base_salary field

6. **Expected Result**: ✅ Base salary should be 8,000,000 (not 0)

---

## Automated Testing

### Run all bug fix tests:
```bash
ENVIRONMENT=test poetry run pytest apps/payroll/tests/test_payroll_bug_fixes.py -v
```

### Run specific test class:
```bash
# Issue 1
ENVIRONMENT=test poetry run pytest \
  apps/payroll/tests/test_payroll_bug_fixes.py::TestEmployeeResignationPayrollImpact -v

# Issue 2
ENVIRONMENT=test poetry run pytest \
  apps/payroll/tests/test_payroll_bug_fixes.py::TestContractEmployeeTypeUpdate -v

# Issue 3
ENVIRONMENT=test poetry run pytest \
  apps/payroll/tests/test_payroll_bug_fixes.py::TestContractAppendixPayrollRecalculation -v

# Issue 4
ENVIRONMENT=test poetry run pytest \
  apps/payroll/tests/test_payroll_bug_fixes.py::TestResignedEmployeeContractRetrieval -v
```

---

## Database Verification Queries

### Check employee data caching:
```sql
-- Should show cached employee data that doesn't change after recalculation
SELECT
    id, code, employee_code, employee_name,
    department_name, position_name, base_salary
FROM payroll_payroll_slip
WHERE employee_id = '{employee_id}'
ORDER BY created_at DESC;
```

### Check employee type updates:
```sql
-- Should show updated employee_type after contract activation
SELECT
    e.id, e.code, e.fullname, e.employee_type,
    c.id as contract_id, c.status as contract_status,
    ct.employee_type as contract_employee_type
FROM hrm_employee e
LEFT JOIN hrm_contract c ON c.employee_id = e.id AND c.status = 'active'
LEFT JOIN hrm_contract_type ct ON ct.id = c.contract_type_id
WHERE e.id = '{employee_id}';
```

### Check resigned employee contracts:
```sql
-- Should find contracts even with EXPIRED status
SELECT
    c.id, c.code, c.status, c.effective_date, c.base_salary,
    e.fullname, e.status as employee_status, e.resignation_start_date
FROM hrm_contract c
JOIN hrm_employee e ON e.id = c.employee_id
WHERE e.status = 'resigned'
    AND c.effective_date <= '{end_of_month}'
ORDER BY c.effective_date DESC;
```

---

## Common Issues & Troubleshooting

### Issue: Payroll not recalculating after contract appendix
**Solution**: Check Celery is running and processing tasks
```bash
# Check Celery status
celery -A config inspect active

# Monitor task queue
celery -A config flower
```

### Issue: Employee type not updating
**Solution**: Ensure signal is registered
```python
# In Django shell
from apps.hrm.signals import contract
print(contract.update_employee_type_on_contract_change)
# Should print function object
```

### Issue: Resigned employee shows base_salary = 0
**Solution**: Check contract status
```sql
SELECT status FROM hrm_contract
WHERE employee_id = '{employee_id}'
ORDER BY effective_date DESC LIMIT 1;
```

---

## Performance Notes

- All payroll recalculations are asynchronous via Celery
- Contract signals trigger tasks, not synchronous recalculation
- Large batch operations may take a few minutes to complete
- Monitor task queue if recalculations seem slow

---

## Rollback Procedure

If issues are found after deployment:

1. **Revert code changes**:
   ```bash
   git revert <commit-hash>
   ```

2. **For employee_type sync issues**:
   ```python
   # Manually sync employee types if needed
   from apps.hrm.models import Contract, Employee
   for contract in Contract.objects.filter(status='active'):
       if contract.contract_type:
           contract.employee.employee_type = contract.contract_type.employee_type
           contract.employee.save(update_fields=['employee_type'])
   ```

3. **For incorrect payroll data**:
   ```python
   # Recalculate all slips in a period
   from apps.payroll.models import SalaryPeriod
   from apps.payroll.services.payroll_calculation import PayrollCalculationService

   period = SalaryPeriod.objects.get(month__year=2025, month__month=1)
   for slip in period.payroll_slips.all():
       calculator = PayrollCalculationService(slip)
       calculator.calculate()
   ```
