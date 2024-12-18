from django.conf import settings
from django.db import models
from model_utils.models import TimeStampedModel

from dynforms.models import DynEntryMixin

User = getattr(settings, "AUTH_USER_MODEL")


class Feedback(DynEntryMixin):
    user = models.ForeignKey(User, related_name='+', null=True, on_delete=models.SET_NULL)
    beamline = models.ForeignKey('beamlines.Facility', null=True, on_delete=models.SET_NULL, related_name="feedback")
    cycle = models.ForeignKey('proposals.ReviewCycle', null=True, on_delete=models.SET_NULL, related_name="feedback")

    class Meta:
        ordering = ["beamline__acronym"]
