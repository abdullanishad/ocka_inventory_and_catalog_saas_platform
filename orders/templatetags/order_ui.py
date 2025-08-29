from django import template
from django.utils.safestring import mark_safe

register = template.Library()

STATUS_STYLES = {
    "pending":   ("bg-amber-100 text-amber-700", "Pending"),
    "confirmed": ("bg-emerald-100 text-emerald-700", "Confirmed"),
    "shipped":   ("bg-blue-100 text-blue-700", "Shipped"),
    "delivered": ("bg-green-100 text-green-700", "Delivered"),
}

@register.simple_tag
def status_badge(status_key: str):
    classes, label = STATUS_STYLES.get(status_key, ("bg-gray-100 text-gray-700", (status_key or "").title()))
    html = f'<span class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm {classes}">{label}</span>'
    return mark_safe(html)

@register.filter
def dict_get(d, key):
    """Safely fetch dict[key] inside templates"""
    try:
        return d.get(key, 0)
    except Exception:
        return 0
