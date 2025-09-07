from django.conf import settings
from django.db import models
from model_utils.models import TimeStampedModel

from dynforms.models import BaseFormModel

User = getattr(settings, "AUTH_USER_MODEL")


class Feedback(BaseFormModel):
    user = models.ForeignKey(User, related_name='+', null=True, on_delete=models.SET_NULL)
    beamline = models.ForeignKey('beamlines.Facility', null=True, on_delete=models.SET_NULL, related_name="feedback")
    cycle = models.ForeignKey('proposals.ReviewCycle', null=True, on_delete=models.SET_NULL, related_name="feedback")

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Feedback #{self.pk} by {self.user} for {self.beamline} ({self.cycle})"
