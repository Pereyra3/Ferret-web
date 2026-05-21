"""Mexican peso formatting: $1,234.56 (comma thousands, period decimals)."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _to_decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _group_int_part(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    parts = []
    while digits:
        parts.append(digits[-3:])
        digits = digits[:-3]
    return ",".join(reversed(parts))


def format_mxn(value, *, show_sign: bool = True) -> str:
    """
    Format amount as Mexican money: $12,345.67
    Always shows two decimal places (centavos).
    """
    try:
        amount = _to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)

    negative = amount < 0
    amount = abs(amount)
    whole, _, frac = f"{amount:.2f}".partition(".")
    grouped = _group_int_part(whole)
    body = f"{grouped}.{frac}"
    if not show_sign:
        return f"-{body}" if negative else body
    return f"-${body}" if negative else f"${body}"


def format_mxn_plain(value) -> str:
    """Same numeric layout without currency sign (e.g. unit price in a table)."""
    return format_mxn(value, show_sign=False)
