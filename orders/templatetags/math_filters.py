from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()

@register.filter(name='mul')
def mul(value, arg):
    """
    Multiply two values (works with Decimal, int, float, numeric strings).
    Returns a Decimal when possible.
    """
    try:
        v = Decimal(str(value))
        a = Decimal(str(arg))
        return v * a
    except (InvalidOperation, TypeError, ValueError):
        try:
            return float(value) * float(arg)
        except Exception:
            return ''

@register.filter(name='rupee')
def rupee(value):
    """
    Format a numeric value as Indian rupee style with 2 decimals and thousand separators.
    Usage: {{ some_decimal|rupee }} -> "₹1,234.00"
    """
    try:
        v = Decimal(value)
        # use Python formatting; Decimal works with format()
        return "₹" + format(v, ",.2f")
    except Exception:
        try:
            f = float(value)
            return "₹" + format(f, ",.2f")
        except Exception:
            return value
