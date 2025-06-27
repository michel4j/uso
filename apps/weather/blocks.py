import copy

from django.urls import reverse

from misc.blocktypes import BaseBlock, BLOCK_TYPES
from .views import get_weather_context


class WeatherBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "weather/block.html"
    reload_freq = 900
    src_url = reverse("weather-detail")
    priority = 3

    def check_allowed(self, request):
        return request.user.is_authenticated

    def render(self, context):
        ctx = copy.copy(context)
        weather_context = get_weather_context()
        if not weather_context:
            return ""
        ctx.update(weather_context)
        return super().render(ctx)
