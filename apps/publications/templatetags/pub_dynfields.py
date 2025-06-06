from django import template
from publications import models

register = template.Library()


@register.simple_tag(takes_context=True)
def set_subject_areas(context):
    data = models.SubjectArea.objects.filter(category__isnull=True).order_by("code").values_list('pk', 'name')
    values, choices = zip(*data) if data else ([], [])
    context['field'].update({
        'choices': choices,
        'values': values,
    })
    return data


@register.filter
def group_subj_choices(choices, defaults):
    if not isinstance(defaults, dict) or defaults is None:
        defaults = []

    ch = [(v, (v.pk in defaults)) for v in choices]
    return ch
