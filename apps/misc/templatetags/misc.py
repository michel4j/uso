import re
from datetime import datetime, date

from django import template
from django.utils import timezone, timesince
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


@register.simple_tag()
def show_block(block) -> str:
    """
    Checks if a dashboard panel block is allowed to be displayed and renders it if so.
    :param block: instance of a panel block that has a `check_allowed` method and a `render` method.
    :return: string
    """
    if block.check_allowed():
        content = block.render()
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
    """
    Renders a stat card with the provided keyword arguments.
    """
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
def state_tag(state, default="", **kwargs) -> str:
    """
    Returns the key from kwargs that matches the given state. Can be used to map a state to a specific tag or label.
    If no match is found, it returns the default value.
    :param state: value to match against the values in kwargs.
    :param default: default string to return if no match is found.
    :param kwargs: key-value pairs where keys are the tags and values are the states.
    """
    for key, value in kwargs.items():
        if value == state:
            return key
    return default


@register.filter
def from_now(dt, now: datetime = None) -> str:
    """
    Returns a human-readable string indicating how long ago or how long until a given date.
    If the date is in the past, it returns "X time ago", if it is in the future, it returns "in X time".
    combined with the `timesince` and `timeuntil` utilities from Django.

    :param dt: Date or datetime object to compare with the current time.
    :param now:  reference time to compare against; if None, uses the current time.
    :return: string indicating the time difference.
    """
    if now is None:
        now = timezone.now()
    if isinstance(dt, date):
        now = now.date()

    if dt < now:
        return f"{timesince.timesince(dt, now)} ago"
    elif dt > now:
        return f"in {timesince.timeuntil(dt, now)}"
    else:
        return 'now'


@register.simple_tag(takes_context=True)
def report_url(context, report, **kwargs):
    """
    Returns the URL for a report with the given context and report object.
    """
    view = context.get('view')
    if not view:
        raise ValueError("No view found in context to generate report URL.")
    return view.get_link_url(report)


@register.filter(name="human_title")
def human_title(text):
    """
    Converts a string to a more human-readable title format.
    Replaces underscores and hyphens with spaces and capitalizes each word.
    """
    if re.match(r'^[A-Z-\d@]*$', text):
        return text
    text = text.replace('_', ' ')
    text = re.sub(r'^(.)',  lambda m: m.group(1).upper(),  text)
    text = re.sub(r'([ -][a-z])', lambda m: m.group(1).upper(),  text)
    return text