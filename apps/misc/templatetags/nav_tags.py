from django import template
from django.urls import reverse, reverse_lazy

register = template.Library()


@register.simple_tag(takes_context=True)
def active(context, url_name, *args):
    txt = ' '.join(args) if args else 'active'
    matches = current_url_equals(context, url_name)
    return txt if matches else ''


@register.simple_tag(takes_context=True)
def active_root(context, url_name, *args):
    txt = ' '.join(args) if args else 'active'
    matches = current_url_startswith(context, url_name)
    return txt if matches else ''


def current_url_equals(context, url_name):
    try:
        reversed = reverse(url_name)
        return context.get('request').path == reversed
    except:
        return context.get('request').path == url_name


def current_url_startswith(context, url_name):
    try:
        reversed = reverse(url_name)
        return context.get('request').path.startswith(reversed)
    except:
        return context.get('request').path.startswith(url_name)
