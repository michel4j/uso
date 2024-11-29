from datetime import timedelta

from django.db import models
from django.utils import timezone
from model_utils.models import TimeStampedModel

from . import utils


# Create your models here.
class Weather(TimeStampedModel):
    city_code = models.CharField(max_length=20, unique=True)
    city_name = models.CharField(max_length=100)
    conditions = models.JSONField()

    @utils.run_async
    def _update(self):
        cond = utils.get_conditions(city=self.city_code)  # may need to be called async
        if cond:
            self.conditions = cond
            self.save()

    def get_current(self, force=False):
        conditions = self.conditions.copy()
        now = timezone.now()
        if force or (now - self.modified) > timedelta(minutes=30):
            self._update()
        return conditions

    def __str__(self):
        return "{0} [{1}]".format(self.city_name, self.city_code)

    class Meta:
        verbose_name = "Weather Location"
        verbose_name_plural = "Weather Locations"
