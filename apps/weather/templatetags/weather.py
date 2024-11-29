from django import template

register = template.Library()


@register.filter(name="timeofday")
def timeofday(dt):
    if (0 <= dt.hour < 6) or (dt.hour >= 21):
        return 'Overnight'
    if 6 <= dt.hour < 12:
        return 'Morning'
    elif 12 <= dt.hour < 18:
        return 'Afternoon'
    else:
        return 'Evening'
