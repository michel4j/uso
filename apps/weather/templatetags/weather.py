from django import template
import django.utils.timezone as django_timezone
register = template.Library()


@register.filter(name="timeofday")
def timeofday(dt):
    now = django_timezone.now()
    prefix = 'This ' if dt.date() > now.date() else 'Tomorrow '
    if (0 <= dt.hour < 6) or (dt.hour >= 21):
        return f'Overnight'
    if 6 <= dt.hour < 12:
        return f'{prefix}Morning'
    elif 12 <= dt.hour < 18:
        return f'{prefix}Afternoon'
    else:
        return f'{prefix}Evening'
