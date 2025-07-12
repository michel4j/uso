from django import template
from django.utils.safestring import mark_safe

register = template.Library()
from django.conf import settings


@register.filter
def verbose_name(value):
    return value._meta.verbose_name


@register.filter
def modulo(num, val):
    return num % val


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
        content = block.render(context)
        return mark_safe(content) if content else ""
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


@register.inclusion_tag('misc/stat-card.html')
def stat_card(**kwargs):
    return kwargs


@register.simple_tag(name='css_overrides')
def css_overrides():
    """
    Returns the CSS overrides for the current theme.
    """
    styles = ""
    for style in getattr(settings, "USO_STYLE_OVERRIDES", []):
        styles += f"<link rel='stylesheet' href='{settings.MEDIA_URL}css/{style}'>\n"
    return mark_safe(styles)


@register.simple_tag(name='state_tag')
def state_tag(state, default="", **kwargs):
    for key, value in kwargs.items():
        if value == state:
            return key
    return default
