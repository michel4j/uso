

import calendar
from datetime import date, datetime

from django import template
from django.utils import timesince
from django.utils import timezone
from django.utils.html import avoid_wrapping

register = template.Library()


@register.filter
def ago(value):
    return timefrom(value)


@register.filter
def remaining(value):
    return timefrom(value, reverse=True, over="overdue")


def timefrom(value, reverse=False, over=""):
    """
    For date and time values shows how many seconds, minutes or hours ago
    compared to current timestamp returns representing string.
    """
    if not isinstance(value, date):  # datetime is a subclass of date
        return value
    chunks = (
        (60 * 60 * 24 * 365, '{0} {1}Y {2}'),
        (60 * 60 * 24 * 30, '{0} {1}m {2}'),
        (60 * 60 * 24 * 7, '{0} {1}w {2}'),
        (60 * 60 * 24, '{0} {1}d {2}'),
        (60 * 60, '{0} {1}h {2}'),
        (60, '{0} {1}min {2}')
    )

    now = timezone.now()
    # Convert datetime.date to datetime.datetime for comparison.
    if not isinstance(value, datetime):
        value = timezone.make_aware(datetime.combine(value, datetime.min.time()), timezone.get_default_timezone())
    delta = (value - now) if reverse else (now - value)
    prefix = 'in' if reverse else ''
    suffix = 'ago' if not reverse else ''
    since = delta.days * 24 * 60 * 60 + delta.seconds
    if since < 0:
        # d is in the future compared to now, stop processing.
        return avoid_wrapping(over)
    elif since < 60:
        return avoid_wrapping('now')
    for (seconds, name) in chunks:
        count = since // seconds
        if count != 0:
            break
    result = avoid_wrapping(name.format(prefix, count, suffix))
    return result


@register.filter
def age(bday, d=None):
    if d is None:
        d = date.today()
        d = date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
    return (d.year - bday.year) - int((d.month, d.day) < (bday.month, bday.day))


@register.filter
def fromnow(dt, now=None):
    if now is None:
        now = timezone.now()
    if isinstance(dt, date):
        now = now.date()

    if dt < now:
        return timesince.timesince(dt, now)
    elif dt > now:
        return timesince.timeuntil(dt, now)
    else:
        return 'now'
