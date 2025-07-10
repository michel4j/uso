from django import template
from django.db.models import Q, Sum, Count, Avg
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.safestring import mark_safe

from projects import models

register = template.Library()


@register.filter(name="get_allocations")
def get_allocations(project, bl):
    return project.active_allocations().filter(beamline=bl)


@register.filter(name="beamline_allocations")
def beamline_allocations(project, bl):
    return project.allocations.filter(beamline=bl)


@register.simple_tag
def get_cycle_requests(facility, cycle):
    return models.ShiftRequest.objects.filter(allocation__beamline=facility).pending()


@register.filter(name="beamline_sessions")
def beamline_sessions(project, bl):
    return models.Session.objects.filter(project=project, beamline=bl)


@register.filter(name="beamline_shifts")
def beamline_shifts(project, bl):
    return project.used_shifts(bl)


@register.filter(name="sample_state_display")
def sample_state_display(sample):
    full_state = sample.full_state()
    prefix = 'Expired' if full_state == sample.STATES.expired else 'Expires'
    full_display = sample.STATES[full_state] if not sample.expiry else f'{prefix} {sample.expiry.isoformat()}'

    if full_state == sample.STATES.approved:
        return f"<i class='bi-check-circle-fill icon-fw text-success'></i>&nbsp;{full_display}"
    elif full_state == sample.STATES.pending:
        return f"<i class='bi-hourglass icon-fw text-body-secondary'></i>&nbsp;{full_display}"
    elif full_state == sample.STATES.rejected:
        return f"<i class='bi-ban icon-fw text-danger'></i>&nbsp;{full_display}"
    elif full_state == sample.STATES.expired:
        return f"<i class='bi-ban icon-fw text-danger'></i>&nbsp;{full_display}"


@register.filter(name="permission_code")
def permission_code(bl, code):
    return "{0}-{1}".format(bl.acronym.upper(), code.upper())


@register.filter
def get_item(dictionary, key):
    if dictionary:
        if dictionary.get(key):
            return dictionary.get(key)
        else:
            return dictionary.get(str(key))
    return None


@register.filter
def get_time(start, end):
    now = timezone.now()
    if now >= start and ((not end) or (now <= end)):
        return now
    elif now < start:
        return start
    return end


@register.filter
def get_time_class(start, end):
    now = timezone.now()
    if start <= now <= end:
        return "text-success"
    elif now < start:
        return "text-info"
    return "text-body-secondary"


@register.simple_tag(takes_context=True)
def get_project_permissions(context, project, facility=None):
    return project.permissions(bl=facility)


@register.simple_tag(takes_context=True)
def get_session_types(context):
    DESCRIPTIONS = {
        models.Session.TYPES.onsite: "Users will be physically at the facility to perform the experiments",
        models.Session.TYPES.remote: "Users will not be at the facility but will connect through the internet to perform the experiments",
        models.Session.TYPES.mailin: "Staff will be performing the experiment on behalf of the users. The users will not be coming to the facility",
    }
    return [(code, label, DESCRIPTIONS.get(code, '')) for code, label in models.Session.TYPES]


@register.simple_tag(takes_context=True)
def show_project_roles(context, project, user):
    roles = []
    if user == project.spokesperson:
        roles.append(('S', 'Spokesperson'))
    if project.leader and user == project.leader:
        roles.append(('L', 'Project Leader'))
    if project.delegate and user == project.delegate:
        roles.append(('D', 'Delegate'))
    role_texts = ['<text title="{1}">{0}</text>'.format(*r) for r in roles]
    return mark_safe(
        '&nbsp;(<strong class="text-primary">{}</strong>)'.format(', '.join(role_texts)) if roles else '')


@register.filter
def material_state_icon(material):
    return {
        'approved': 'bi-check2-square text-success',
        'denied': 'bi-ban text-danger',
        'pending': 'bi-hourglass',
    }.get(material.state, '')


@register.filter
def no_equipment(beamlines):
    return beamlines.exclude(kind='equipment')


@register.filter
def risk_background(material):
    return {
        0: 'bg-white text-body-secondary',
        1: 'bg-success',
        2: 'bg-info',
        3: 'bg-warning',
        4: 'bg-danger',
    }.get(material.risk_level, '')


@register.inclusion_tag('projects/event-icon.html', takes_context=True)
def event_icon(context, event_time, icon="bi-calendar2-event", size="icon-lg", description=""):
    return {
        'size': size,
        'icon': icon,
        'description': description,
        'event_time': event_time
    }


@register.simple_tag(takes_context=False)
def get_facility_cycle_stats(facility, cycle):

    reservations = models.Reservation.objects.filter(beamline=facility, cycle=cycle)
    total = cycle.schedule.normal_shifts()
    unavailable = reservations.filter(kind__in=['', None]).aggregate(total=Coalesce(Sum('shifts'), 0))

    aggregations = {
        'total': Count('id', distinct=True),
        'shifts': Sum('allocations__shifts'),
        'avg_shifts': Avg('allocations__shifts'),
    }
    active_projects = models.Project.objects.filter(
        Q(allocations__beamline=facility) | Q(allocations__beamline__parent=facility),
        allocations__cycle=cycle
    ).distinct()
    new_projects = active_projects.filter(cycle=cycle)

    return {
        'total_shifts': total,
        'available_shifts': total - unavailable['total'],
        'active': active_projects.aggregate(**aggregations),
        'new': new_projects.aggregate(**aggregations),
    }


@register.simple_tag(takes_context=True)
def get_equipment_list(context, data=()):
    if not 'review' in context:
        return []

    review = context['review']
    material = review.reference
    if not material:
        return []

    info = {
        item['name']: item.get('decision', "")
        for item in data if item.get('decision')
    }

    equipment_list = []
    for item in material.equipment:
        new_item = item.copy()
        decision = info.get(new_item['name'], new_item.get('decision', ''))
        if decision:
            new_item['decision'] = decision
        equipment_list.append(new_item)

    return equipment_list
