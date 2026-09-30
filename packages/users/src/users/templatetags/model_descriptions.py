# s. https://stackoverflow.com/questions/42826287/model-description-in-django-admin

from django import template
from django.utils.html import escape, mark_safe

register = template.Library()


@register.simple_tag()
def model_desc(obj):
    """
    Return the model docstring wrapped in a ``<p>`` tag for admin display.

    The docstring is developer-authored trusted content; it is escaped before
    being wrapped so any special characters render literally.
    """
    if obj.__doc__:
        return mark_safe(f"<p>{escape(obj.__doc__)}</p>")  # noqa: S308
    return ""
