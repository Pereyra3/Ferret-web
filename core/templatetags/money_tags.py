from decimal import Decimal, InvalidOperation

from django import template

from core.money import format_mxn, format_mxn_plain

register = template.Library()


@register.filter(name="qty")
def qty_filter(value):
    """Cantidad sin ceros sobrantes: 5.000 -> 5, 5.500 -> 5.5."""
    if value is None or value == "":
        return "—"
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return value
    d = d.normalize()
    return f"{d:f}"


@register.filter(name="mxn")
def mxn_filter(value):
    """Moneda MXN con signo: $1,234.56"""
    if value is None or value == "":
        return "—"
    return format_mxn(value)


@register.filter(name="mxn_plain")
def mxn_plain_filter(value):
    """Importe sin signo $ (misma separación miles/decimales)."""
    if value is None or value == "":
        return "—"
    return format_mxn_plain(value)
