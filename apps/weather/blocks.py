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

    def get_context_data(self):
        ctx = super().get_context_data()
        weather_context = get_weather_context()
        if weather_context:
            ctx.update(weather_context)
        else:
            self.visible = False
        return ctx
