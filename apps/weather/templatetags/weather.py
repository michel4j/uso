from django import template
from django.utils import timezone
register = template.Library()


@register.filter(name="timeofday")
def timeofday(dt):
    now = timezone.localtime(timezone.now())
    dt = timezone.localtime(dt)

    prefix = 'This ' if dt.date() == now.date() else 'Tomorrow '
    if (0 <= dt.hour < 4) or (dt.hour >= 20):
        text = f'Overnight'
    elif 4 <= dt.hour < 12:
        text = f'{prefix}Morning'
    elif 12 <= dt.hour < 16:
        text = f'{prefix}Afternoon'
    else:
        text = f'{prefix}Evening'
    return text
