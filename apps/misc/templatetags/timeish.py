
from datetime import datetime, date

from django import template
from django.utils import timezone, timesince


register = template.Library()


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

