from datetime import datetime, timezone

from django.utils import timezone as django_timezone
from django.views.generic import TemplateView

from . import models
from .utils import ICON_MAP_DAY, ICON_MAP_NIGHT


def get_weather_context():
    ctx = {}
    obj = models.Weather.objects.filter(pk=1).first()
    if not obj: return
    ctx['location'] = obj
    conditions = obj.get_current()
    now = django_timezone.now()
    sunrise = datetime.fromtimestamp(conditions['current']['sys']['sunrise'], tz=timezone.utc)
    sunset = datetime.fromtimestamp(conditions['current']['sys']['sunset'], tz=timezone.utc)

    icon_map = ICON_MAP_NIGHT if (now.hour > sunset.hour or now.hour < sunrise.hour) else ICON_MAP_DAY
    ctx['weather'] = {
        'time': datetime.fromtimestamp(conditions['current']['dt'], tz=timezone.utc),
        'temp': conditions['current']['main']['temp'],
        'windchill': conditions['current']['main']['windchill'],
        'description': conditions['current']['weather'][0]['description'],
        'icon': icon_map.get(conditions['current']['weather'][0]['id']),
        'forecast': [],
    }
    for f in conditions['forecast']:
        dt = datetime.fromtimestamp(f['dt'], tz=timezone.utc)
        icon_map = ICON_MAP_NIGHT if (dt.hour > sunset.hour or dt.hour < sunrise.hour) else ICON_MAP_DAY
        dt = django_timezone.localtime(dt)
        if dt.hour not in [6, 12, 18, 0]: continue
        ctx['weather']['forecast'].append({
            'time': dt,
            'temp': f['main']['temp'],
            'windchill': f['main']['windchill'],
            'description': f['weather'][0]['description'],
            'icon': icon_map.get(f['weather'][0]['id']),
        })
        if len(ctx['weather']['forecast']) == 3:
            break
    return ctx


class WeatherDetailView(TemplateView):
    template_name = "weather/snippet.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ctx = get_weather_context()
        if ctx:
            context.update(ctx)
        return context