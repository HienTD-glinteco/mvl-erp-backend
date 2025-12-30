# Payroll Signals

This directory contains all signal handlers for the payroll app, organized by purpose.

## Structure

```
signals/
├── __init__.py                    # Imports all signal modules
├── code_generation.py             # Auto-code generation for models
├── kpi_assessment.py              # KPI assessment status and notifications
├── payroll_recalculation.py       # Triggers for payroll recalculation
├── statistics_update.py           # SalaryPeriod statistics updates
├── deadline_validation.py         # Business deadline enforcement
└── SIGNALS_DOCUMENTATION.md       # Complete documentation
```

## Quick Reference

### Code Generation
- **SalaryPeriod**: `SP_{YYYYMM}`
- **PayrollSlip**: `PS_{YYYYMM}_{seq}`
- **SalesRevenue**: `SR-{YYYYMM}-{seq}`
- **RecoveryVoucher**: `RV-{YYYYMM}-{seq}`
- **PenaltyTicket**: `RVF-{YYYYMM}-{seq}`

### Signal Flow

```
Data Change → Recalculation Signal → Celery Task → PayrollSlip.save → Statistics Update
```

### Key Principles

1. **No Duplicate Updates**: Statistics are updated centrally via `PayrollSlip.post_save`
2. **Async Processing**: Heavy calculations use Celery tasks
3. **Deadline Enforcement**: Pre-save signals block invalid operations
4. **Clear Separation**: Each file handles one specific concern

## Documentation

For detailed documentation, see [SIGNALS_DOCUMENTATION.md](./SIGNALS_DOCUMENTATION.md)

## Adding New Signals

1. Identify the category (code generation, KPI, recalculation, statistics, or validation)
2. Add to the appropriate file
3. Update `__init__.py` if creating a new category
4. Document in `SIGNALS_DOCUMENTATION.md`
5. Test thoroughly to avoid duplicate processing
