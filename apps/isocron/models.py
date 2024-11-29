from django.db import models
from model_utils import Choices


class JobLog(models.Model):
    STATES = Choices(
        ('never', 'Never Ran'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )
    code = models.CharField(max_length=255, unique=True)
    ran_at = models.DateTimeField(auto_now=True)
    state = models.CharField(max_length=20, choices=STATES, default=STATES.never)
    message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.code} ({self.get_state_display()})'

    class Meta:
        app_label = 'isocron'
