from decimal import ROUND_HALF_UP, Decimal
from typing import Union

DECIMAL_ZERO = Decimal("0.00")


def quantize_decimal(val: Union[Decimal, int, float, str, None]) -> Decimal:
    if val is None:
        return DECIMAL_ZERO
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
