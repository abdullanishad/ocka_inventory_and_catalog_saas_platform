from django import template
from catalog.models import Size

register = template.Library()

@register.filter
def get_size_name(size_id):
    """Return size name given its ID."""
    try:
        return Size.objects.get(id=size_id).name
    except Size.DoesNotExist:
        return "?"
