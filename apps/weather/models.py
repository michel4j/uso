from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from model_utils.models import TimeStampedModel

from . import utils

UPDATE_INTERVAL = timedelta(minutes=30)
WEATHER_LOCATION = getattr(settings, 'USO_WEATHER_LOCATION', [52.14, -106.63])


class Weather(TimeStampedModel):
    lat = models.FloatField(blank=True, null=True)
    lon = models.FloatField(blank=True, null=True)
    city_name = models.CharField(max_length=100, blank=True, null=True)
    conditions = models.JSONField(default=dict, blank=True, null=True)

    def update_conditions(self):
        cond = utils.get_conditions()
        if cond:
            self.conditions = cond
            self.save()

    @utils.run_async
    def async_update_conditions(self):
        """
        Asynchronously update the weather conditions.
        This method is intended to be run in a separate thread.
        """
        self.update_conditions()

    def update_location(self):
        """
        Update the location information for the weather service.
        """
        info = utils.get_location_info()
        if info:
            self.city_name = f"{info['name']}, {info['country']}"
            self.lat, self.lon = WEATHER_LOCATION
            self.save()

    def get_current(self, force=False):
        """
        Get current weather conditions, updating them if necessary.
        :param force:
        :return:
        """
        lat, lon = WEATHER_LOCATION
        if self.lat != lat or self.lon != lon:
            self.update_location()
            self.update_conditions()
        elif not self.conditions:
            self.update_conditions()

        conditions = self.conditions
        now = timezone.now()
        if force or (now - self.modified) > UPDATE_INTERVAL:
            self.async_update_conditions()

        return conditions

    def __str__(self):
        return self.city_name

    class Meta:
        verbose_name = "Weather Data"
        verbose_name_plural = "Weather Data"
