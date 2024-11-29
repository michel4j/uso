from django import template
from django.db.models import Q
from publications import models

register = template.Library()


@register.simple_tag(takes_context=True)
def get_subject_areas(context):
    return models.SubjectArea.objects.filter(category__isnull=True).order_by("code")


@register.filter
def group_subj_choices(choices, defaults):
    if not isinstance(defaults, dict) or defaults is None:
        defaults = []

    ch = [(v, (v.pk in defaults)) for v in choices]
    return ch
