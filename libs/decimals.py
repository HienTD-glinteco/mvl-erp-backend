from decimal import ROUND_HALF_UP, Decimal
from typing import Union

DECIMAL_ZERO = Decimal("0.00")


def quantize_decimal(val: Union[Decimal, int, float, str, None]) -> Decimal:
    if val is None:
        return DECIMAL_ZERO
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_currency(value: Decimal, decimal_places: int = 0) -> Decimal:
    """Round currency to VND format with Excel-compatible rounding.

    Uses ROUND_HALF_UP to match Excel's ROUND function behavior,
    preventing 1 VND discrepancies in payroll calculations.

    Args:
        value: Amount to round
        decimal_places: Number of decimal places (default 0 for VND)

    Returns:
        Rounded decimal value
    """
    if decimal_places == 0:
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    else:
        quantizer = Decimal(10) ** -decimal_places
        return value.quantize(quantizer, rounding=ROUND_HALF_UP)
