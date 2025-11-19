from decimal import ROUND_HALF_UP, Decimal

DECIMAL_ZERO = Decimal("0.00")


def quantize_decimal(val: Decimal) -> Decimal:
    if val is None:
        return DECIMAL_ZERO
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
