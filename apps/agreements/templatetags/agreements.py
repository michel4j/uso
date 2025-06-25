from django import template

from agreements import models

register = template.Library()


@register.filter(name="active_agreements")
def active_agreements(user):
    return models.Acceptance.objects.filter(user=user, active=True)
