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


class Category(models.Model):
    """
    Stores a distinct category of feedback, such as 'machine', 'beamline',
    or 'amenities'. This allows for dynamically adding new categories in the future.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Rating(models.Model):
    """
    Stores an individual rating item. This is the core data model
    """
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name='ratings')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='ratings')
    name = models.CharField(max_length=100)     # e.g., 'Reliability', 'Personnel'
    label = models.CharField(max_length=100)    # e.g., 'Excellent', 'Very Poor'
    value = models.IntegerField()               # e.g., 5, 1

    class Meta:
        # Add a composite index for faster filtering and ordering.
        indexes = [
            models.Index(fields=['feedback', 'category']),
        ]
        # Ensure that for a single feedback submission, each metric is rated only once.
        unique_together = ('feedback', 'category', 'name')

    def __str__(self):
        return f"{self.category.name} - {self.name}: {self.value}"
