from django import template
from django.utils.safestring import mark_safe

register = template.Library()
from django.conf import settings


@register.filter
def verbose_name(value):
    return value._meta.verbose_name


@register.filter
def verbose_name_plural(value):
    return value._meta.verbose_name_plural


@register.simple_tag
def version():
    return getattr(settings, 'VERSION', '')


@register.simple_tag(takes_context=True)
def show_block(context, block):
    request = context['request']
    if block.check_allowed(request):
        return mark_safe(block.render(context))
    else:
        return ""


@register.simple_tag(name='store', takes_context=True)
def store(context, name, value):
    key = '__accum__' + name
    context[key] = context.get(key, 0) + value
    return context[key]


@register.simple_tag(name='spend', takes_context=True)
def spend(context, name, value):
    key = '__accum__' + name
    context[key] = context.get(key, 0) + value
    return context[key]


@register.simple_tag(takes_context=True)
def define(context, **kwargs):
    for k, v in list(kwargs.items()):
        context[k] = v
