from django import template
from django.db.models import Case, When, Value, BooleanField

from beamlines import models

register = template.Library()


@register.simple_tag(takes_context=True)
def get_ancillaries(context, data={}):
    if not isinstance(data, dict):
        data = {}
    selected_labs = data.get('labs', [0])
    selected_equipment = data.get('equipment', [0])
    ancillaries = {
        'labs': models.Lab.objects.filter(available=True).annotate(
            selected=Case(When(pk__in=selected_labs, then=Value(1)), default=Value(0), output_field=BooleanField())
        ),
        'equipment': models.Ancillary.objects.filter(available=True).annotate(
            selected=Case(When(pk__in=selected_equipment, then=Value(1)), default=Value(0), output_field=BooleanField())
        ),
    }
    return ancillaries


@register.simple_tag(takes_context=True)
def get_selected_ancillaries(context, data={}):
    if not isinstance(data, dict):
        data = {}
    selected_labs = data.get('labs', [0])
    selected_equipment = data.get('equipment', [0])
    ancillaries = {
        'labs': models.Lab.objects.filter(available=True, pk__in=selected_labs),
        'equipment': models.Ancillary.objects.filter(available=True, pk__in=selected_equipment),
    }
    return ancillaries


@register.simple_tag(takes_context=True)
def get_facility_tags(context, data=[]):
    _all = models.FacilityTag.objects.filter()
    _sel = models.FacilityTag.objects.filter(pk__in=data, active=True)
    ancillaries = {
        'selected': _sel,
        'all': [(obj, obj in _sel) for obj in _all],
    }
    return ancillaries


@register.filter(name="get_color")
def get_color(st):
    colors = {
        'design': '#9edae5',
        'construction': '#c5b0d5',
        'commissioning': '#fd8d3c',
        'operating': '#74c476',
        'decommissioned': '#d62728',
        'abstaining': '#dddddd'
    }
    return colors.get(st, '#dddddd')


@register.filter(name="get_facility")
def get_facility(pk):
    return models.Facility.objects.get(pk=pk)


@register.filter(name="is_user")
def is_user(user, beamline):
    return beamline.is_user(user)


@register.filter(name="is_staff")
def is_staff(user, beamline):
    return beamline.is_staff(user)


@register.filter(name="is_admin")
def is_admin(user, beamline):
    return beamline.is_admin(user)


@register.filter(name="is_remote_user")
def is_remote_user(user, beamline):
    return beamline.is_user(user, remote=True)

@register.filter(name="get_state")
def get_state(t):
    return t.state


@register.filter(name="filtered_list", takes_context=True)
def filtered_list(filters):
    data = [type(f[2]) == type('') for f in filters]
    return any(data)


@register.filter(name="sectors")
def sectors(obj_list):
    return [o for o in obj_list if o.kind in ['village', 'sector']]


@register.filter(name="get_tracks")
def get_tracks(f):
    if f.techniques.all():
        return ', '.join([t[0] for t in f.techniques.all().values_list('track__acronym').distinct()])
    return ""

@register.inclusion_tag("beamlines/fields/facility-details.html", takes_context=True)
def show_facility_details(context, fac_id=0):
    facility = models.Facility.objects.get(pk=fac_id)

    endstations = [(v.pk, v.name) for v in facility.endstations.all()]
    techniques = [(v.pk, v.name) for v in facility.techniques.all()]

    return {
        'endstations': endstations,
        'techniques': techniques,
        'data': context['data'],
        'field': context['field'],
    }
