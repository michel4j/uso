from datetime import datetime, timezone, timedelta

from django.utils import timezone as django_timezone
from django.views.generic import TemplateView

from . import models
from .utils import ICON_MAP_DAY, ICON_MAP_NIGHT


def get_weather_context():
    ctx = {}
    weather = models.Weather.objects.filter().first()
    if not weather:
        return ctx
    ctx['location'] = weather
    conditions = weather.get_current()
    if not conditions:
        return ctx
    now = django_timezone.now()
    sunrise = datetime.fromtimestamp(conditions['current']['sunrise'], tz=timezone.utc)
    sunset = datetime.fromtimestamp(conditions['current']['sunset'], tz=timezone.utc)

    icon_map = ICON_MAP_NIGHT if (now.hour > sunset.hour or now.hour < sunrise.hour) else ICON_MAP_DAY
    ctx['weather'] = {
        'time': datetime.fromtimestamp(conditions['current']['dt'], tz=timezone.utc),
        'temp': conditions['current']['temp'],
        'temp_min': conditions['current']['temp_min'],
        'temp_max': conditions['current']['temp_max'],
        'feels_like': conditions['current']['feels_like'],
        'description': conditions['current']['weather'][0]['description'],
        'icon': icon_map.get(conditions['current']['weather'][0]['id']),
        'forecast': [],
    }
    for forecast in conditions['forecast']:
        dt = datetime.fromtimestamp(forecast['dt'], tz=timezone.utc)
        icon_map = ICON_MAP_NIGHT if (dt.hour > sunset.hour or dt.hour < sunrise.hour) else ICON_MAP_DAY
        dt = django_timezone.localtime(dt)
        if dt - now < timedelta(hours=3):
            continue
        if dt.hour not in [6, 12, 18, 0]:
            continue
        ctx['weather']['forecast'].append({
            'time': dt,
            'temp': forecast['temp'],
            'feels_like': forecast['feels_like'],
            'description': forecast['weather'][0]['description'],
            'icon': icon_map.get(forecast['weather'][0]['id']),
            'temp_min': forecast['temp_min'],
            'temp_max': forecast['temp_max'],
        })
        if len(ctx['weather']['forecast']) == 3:
            break
    return ctx


class WeatherDetailView(TemplateView):
    template_name = "weather/block.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ctx = get_weather_context()

        if ctx:
            context.update(ctx)
        return context

