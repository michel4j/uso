from django import template
from datetime import datetime
from django.utils import timezone
import calendar

from beamlines.models import Facility
from ..models import ModeType

register = template.Library()

MODE_COLORS = {
    'N': '#99cc00',
    'NS': '#739900',
    'D': '#ff9900',
    'DS': '#cc7a00',
    'X': '#ffff99',
    'M': '#00ccff',
    'NS-SB': '#739900',
    'DS-CSR': '#cc7a00',
}
TIME = {
    8: 0,
    16: 1,
    24: 2
}


@register.filter
def get_mode_color(mode):
    return MODE_COLORS[mode]


@register.simple_tag
def get_mode_types():
    return ModeType.objects.all()


@register.filter
def get_day_shifts(shifts):
    s = {}
    for sh in shifts:
        d = datetime.strftime(sh.start_time, "%Y-%m-%d")
        if d not in s:
            s[d] = ['', '', '']
        s[d][TIME[sh.start_time.hour]] = str(sh.mode.mode_type)
    return s


@register.simple_tag(takes_context=False)
def get_color_dict():
    return MODE_COLORS


@register.simple_tag(takes_context=False)
def get_facilities():
    return [str(bl.acronym.replace('@', 'at')) for bl in Facility.objects.all()]


@register.filter
def any_in(i):
    return any(i)


@register.filter
def get_range(i):
    return list(range(i))


@register.filter
def month_name(month_number):
    return calendar.month_name[month_number]


wk = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']


@register.filter
def from_first(dt):
    return wk[:(dt.weekday() + 1) % 7]


@register.filter
def from_last(dt, days):
    wkdays = [wk[i % 7] for i in range(days)]
    extras = days - dt.day - (datetime(dt.year, dt.month, 1).weekday() + 1) % 7
    return extras and wkdays[-extras:] or []


@register.filter
def get_day_shift(dt, data):
    return timezone.make_aware(dt) in data and data[timezone.make_aware(dt)] or None


@register.filter
def get_shift(dt):
    return (dt.hour == 0 and 'Night') or (dt.hour == 8 and 'Day') or 'Evening'
