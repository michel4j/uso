from django.core.serializers import serialize
from django.db.models.query import QuerySet
from django.utils.safestring import mark_safe
import json
from django.template import Library

register = Library()


@register.filter(name="jsonify", needs_autoescape=True)
def jsonify(obj, autoescape=None):
    if isinstance(obj, QuerySet):
        out = json.dumps(list(obj))
    elif isinstance(obj, QuerySet):
        out = serialize('json', obj)
    else:
        out = json.dumps(obj)
    return mark_safe(out)
