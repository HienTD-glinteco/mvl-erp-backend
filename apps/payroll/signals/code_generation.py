"""Code generation signals for payroll models.

This module handles automatic code generation for models using AutoCodeMixin.
Codes are generated in specific formats after instance creation.

Models:
- SalaryPeriod: SP_{YYYYMM}
- PayrollSlip: PS_{YYYYMM}_{id}
- SalesRevenue: SR-{YYYYMM}-{seq}
- RecoveryVoucher: RV-{YYYYMM}-{seq}
- PenaltyTicket: RVF-{YYYYMM}-{seq}
"""

from apps.payroll.models import (
    PayrollSlip,
    PenaltyTicket,
    RecoveryVoucher,
    SalaryPeriod,
    SalesRevenue,
)
from apps.payroll.models.payroll_slip import generate_payroll_slip_code
from apps.payroll.models.salary_period import generate_salary_period_code
from libs.code_generation import register_auto_code_signal


def generate_sales_revenue_code(instance: SalesRevenue) -> None:
    """Generate sales revenue code in format SR-{YYYYMM}-{seq}.

    Args:
        instance: SalesRevenue instance which MUST have an id and month.

    Raises:
        ValueError: If the instance has no id or month.
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("SalesRevenue must have an id to generate code")

    if not instance.month:
        raise ValueError("SalesRevenue must have a month to generate code")

    year = instance.month.year
    month = instance.month.month
    month_key = f"{year}{month:02d}"

    max_code = (
        SalesRevenue.objects.filter(month=instance.month, code__startswith=f"{SalesRevenue.CODE_PREFIX}-{month_key}-")
        .exclude(pk=instance.pk)
        .values_list("code", flat=True)
    )

    max_seq = 0
    for code in max_code:
        try:
            seq_part = code.split("-")[-1]
            seq = int(seq_part)
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    seq = max_seq + 1
    instance.code = f"{SalesRevenue.CODE_PREFIX}-{month_key}-{seq:04d}"
    instance.save(update_fields=["code"])


def generate_recovery_voucher_code(instance: RecoveryVoucher) -> None:
    """Generate and assign code for RecoveryVoucher in format RV-{YYYYMM}-{seq}.

    Args:
        instance: RecoveryVoucher instance with month set

    Raises:
        ValueError: If month is not set on the instance
    """
    if not instance.month:
        raise ValueError("Month must be set to generate code")

    year_month = instance.month.strftime("%Y%m")
    prefix = f"{RecoveryVoucher.CODE_PREFIX}-{year_month}-"

    existing_codes = (
        RecoveryVoucher.objects.filter(code__startswith=prefix).exclude(pk=instance.pk).values_list("code", flat=True)
    )

    max_seq = 0
    for code in existing_codes:
        try:
            seq_part = code.split("-")[-1]
            seq = int(seq_part)
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    next_seq = max_seq + 1
    instance.code = f"{prefix}{str(next_seq).zfill(4)}"
    instance.save(update_fields=["code"])


def generate_penalty_ticket_code(instance: "PenaltyTicket") -> None:
    """Generate and assign a code for a PenaltyTicket instance.

    Format: RVF-{YYYYMM}-{seq}
    Example: RVF-202511-0001

    Args:
        instance: PenaltyTicket instance which MUST have a non-None id and month

    Raises:
        ValueError: If the instance has no id set or month missing
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("PenaltyTicket must have an id to generate code")

    if not instance.month:
        raise ValueError("PenaltyTicket must have a month to generate code")

    month_str = instance.month.strftime("%Y%m")
    seq = str(instance.id).zfill(4)

    instance.code = f"{PenaltyTicket.CODE_PREFIX}-{month_str}-{seq}"
    instance.save(update_fields=["code"])


# Register auto-code signals
register_auto_code_signal(
    SalaryPeriod,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_salary_period_code,
)

register_auto_code_signal(
    PayrollSlip,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_payroll_slip_code,
)

register_auto_code_signal(
    SalesRevenue,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_sales_revenue_code,
)

register_auto_code_signal(
    RecoveryVoucher,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_recovery_voucher_code,
)

register_auto_code_signal(
    PenaltyTicket,
    temp_code_prefix="TEMP_",
    custom_generate_code=generate_penalty_ticket_code,
)
