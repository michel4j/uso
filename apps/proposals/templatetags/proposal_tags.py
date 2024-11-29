import json
from collections import defaultdict

from users.models import User
from ..models import Proposal, Review
from django import template
from mimetypes import MimeTypes
from proposals import models
from users import utils
from proposals.utils import _color_scale, get_techniques_matrix
import itertools
import functools, operator
from django.db.models import When, BooleanField, Value, Case
from django.utils.safestring import mark_safe

register = template.Library()

STATE_ICON_CLASSES = {
    Proposal.STATES.draft: "bi-file-earmark-richtext icon-1x icon-fw text-muted",
    Proposal.STATES.submitted: "bi-receipt icon-1x icon-fw text-primary",
}

STATE_CLASSES = {
    Proposal.STATES.draft: "text-muted",
    Proposal.STATES.submitted: "text-info",
    Review.STATES.closed: "text-info",
    Review.STATES.pending: "text-warning",
}

RISK_LEVELS = {0: "Unknown", 1: "Low", 2: "Moderate", 3: "High", 4: "Unacceptable", 5: "Unknown"}

FILE_TYPES = {
    'application/pdf': 'bi-filetype-pdf text-danger',
    'image/png': 'bi-filetype-png text-success',
    'image/jpg': 'bi-filetype-jpg text-info',
}


@register.filter
def verbose_name(value):
    return value._meta.verbose_name


@register.filter
def verbose_name_plural(value):
    return value._meta.verbose_name_plural


@register.filter
def human_role(role):
    name, realm = (role, '') if ':' not in role else role.split(':')
    if realm:
        return "{} ({})".format(name.replace('-', ' ').title(), realm.upper())
    else:
        return name.replace('-', ' ').title()


@register.filter
def display_scores(review):
    if review.kind == "scientific":
        scores = (
            "<div class='text-center'>"
            "<span title='Merit'>{}</span>&emsp;"
            "<span title='Suitability'>{}</span>&emsp;"
            "<span title='Capability'>{}</span>"
            "</div>"
        ).format(
            review.details.get('scientific_merit', 0),
            review.details.get('suitability', 0),
            review.details.get('capability', 0),
        )
    elif review.kind == "technical":
        scores = (
            "<div class='text-center'>"
            "<span title='Technical Suitability'>{}</span>"
            "</div>"
        ).format(
            review.details.get('suitability', 0),
        )
    elif review.kind in ["safety", "approval"]:
        risk_level = review.details.get('risk_level', 5)
        scores = (
            "<div class='text-center'>"
            "<span title='Risk Level'>{} Risk</span>"
            "</div>"
        ).format(
            RISK_LEVELS.get(risk_level, 'Unknown'),
        )
    else:
        scores = ""
    return mark_safe(scores)


@register.filter
def display_risk_level(review):
    if review.kind in ["safety", "approval", "technical"]:
        risk_level = review.details.get('risk_level', 0)
        risk_text = RISK_LEVELS.get(risk_level)
        text = "<span class='label label-risk{} style='line-height: 18px;'>{}</span>".format(risk_level, risk_text)
        return mark_safe(text)
    else:
        return ""


@register.filter
def display_state(review):
    if review.is_submitted():
        params = {
            'title': 'Complete',
            'style': 'bg-cat-1',
        }
        progress = 100
    elif review.is_complete:
        params = {
            'title': 'Complete',
            'style': 'bg-cat-3 striped',
        }
        progress = max(5, min(100, review.validate().get('progress', 0.0)))
    else:
        params = {
            'title': 'Incomplete',
            'style': 'bg-cat-2 striped',
        }
        progress = max(5, min(100, review.validate().get('progress', 0.0)))
    if review.state == review.STATES.closed:
        params['style'] = 'bg-cat-8'
    elif review.state == review.STATES.pending:
        params['style'] = 'bg-cat-6'
        progress = 0
    params['state_display'] = review.get_state_display()
    params['state'] = 'disabled' if review.state == review.STATES.closed else ''

    params['size'] = "{}%".format(progress)

    state = ('<span class="inline-progress {state}" title="{title}: {state_display}">'
             '<div class="{style}" style="width: {size};"></div></span>').format(**params)
    return mark_safe(state)


@register.simple_tag(takes_context=True)
def get_approval_reviews(context):
    from samples.models import Hazard
    if hasattr(context.get('form', None), 'instance'):
        review = context['form'].instance
    else:
        return models.Review.objects.none()
    reviews = review.reference.reviews.filter(kind__in=["safety", "ethics", "technical", "equipment"])
    rev_list = []
    for r in reviews:
        if r.kind == 'ethics':
            rev_list.append({
                "review": r,
                "rejected": [s['sample'] for s in r.details.get('samples', []) if s['decision'] == 'rejected'],
                "exempt": [s['sample'] for s in r.details.get('samples', []) if s['decision'] == 'exempt'],
                "approved": [s['sample'] for s in r.details.get('samples', []) if
                             s['decision'] in ['protocol', 'ethics']],
                "comments": r.details.get('comments', ''),
                "completeness": r.validate().get('progress'),
            })
        elif r.kind == 'technical':
            rev_list.append({
                "review": r,
                "comments": r.details.get('comments', ''),
                "completeness": r.validate().get('progress'),
            })
        else:
            hazards = functools.reduce(operator.__add__, [s.get('hazards', []) for s in r.details.get('samples', [])],
                                       [])
            rev_list.append(
                {
                    "review": r,
                    "rejected": [s['sample'] for s in r.details.get('samples', []) if s.get('rejected')],
                    "comments": r.comments(),
                    "recommendation": r.details.get('risk_level'),
                    "completeness": r.validate().get('progress'),
                    "hazards": Hazard.objects.filter(pk__in=hazards),
                }
            )
    for submission in review.reference.project.submissions.all():
        technical_reviews = submission.reviews.filter(kind="technical")
        for r in technical_reviews:
            rev_list.append({
                "review": r,
                "comments": r.details.get('comments', ''),
                "completeness": r.validate().get('progress'),
            })
    return rev_list


@register.simple_tag(takes_context=True)
def all_reviews_completed(context):
    if hasattr(context.get('form', None), 'instance'):
        review = context['form'].instance
    else:
        return False
    reviews = review.reference.reviews.filter(kind__in=[review.TYPES.safety, review.TYPES.ethics])
    return 0 < reviews.count() == reviews.complete()


@register.filter
def file_icon(file):
    mime = MimeTypes()
    mt = mime.guess_type(file.path)[0]
    return FILE_TYPES.get(mt, 'bi-file-earmark')


@register.filter(name='state_icon')
def state_icon(value):
    return STATE_ICON_CLASSES.get(value, 'icon-fw')


@register.filter(name='state_color')
def state_color(value):
    return STATE_CLASSES.get(value, 'text-default')


@register.filter(name='relevant_techniques')
def relevant_techniques(techniques, items):
    if not techniques: return []
    return techniques.filter(pk__in=items.values_list('technique__kind__pk', flat=True))


@register.filter(name='relevant_proposals')
def relevant_proposals(reviewer_assignment, reviewer):
    return reviewer_assignment.get(reviewer, [])


@register.filter(name='relevant_areas')
def relevant_areas(reviewer, proposal):
    if reviewer and proposal:
        return set(reviewer.areas.all()) & set(proposal.areas.all())
    else:
        return set()


@register.filter(name='get_conflicts')
def get_conflicts(proposal, conflict_results):
    return conflict_results.get(proposal, [])


@register.filter
def verbose_name(value):
    return value._meta.verbose_name


@register.filter
def verbose_name_plural(value):
    return value._meta.verbose_name_plural


@register.simple_tag(takes_context=True)
def get_options(context, data={}):
    data = {} if not isinstance(data, dict) else data
    sel_techs = [0] + data.get('techniques', [])
    sel_fac = 0 if not data.get('facility') else int(data.get('facility'))
    cycle = models.ReviewCycle.objects.next()
    technique_matrix = get_techniques_matrix(cycle, sel_techs=sel_techs, sel_fac=sel_fac)
    technique_matrix['cycle'] = cycle
    return technique_matrix


@register.simple_tag(takes_context=True)
def get_cycle_options(context):
    data = context.get("data")
    if data:
        context['selected_cycle'] = models.ReviewCycle.objects.filter(pk=data).first()
    options = [(c.pk, c, c == context.get('selected_cycle')) for c in
               [models.ReviewCycle.objects.next(), models.ReviewCycle.objects.current().first()]]
    return options


@register.filter
def team_roles(roles):
    ROLES = {'leader': 'P', 'delegate': 'D', 'spokesperson': 'S'}
    roles = [ROLES.get(r) for r in roles if r in ROLES]
    return '({0})'.format(', '.join(roles)) if roles else ''


@register.inclusion_tag("proposals/facility-reqs.html", takes_context=True)
def show_facility_requirements(context, reqs, cycle=None):
    out_ctx = {'facilities': []}

    for req in reqs:
        beamline = None
        config = None
        if req.get('facility'):
            beamline = models.Facility.objects.get(pk=req['facility'])
            config = beamline.configs.active(cycle=cycle).accepting().first()
        if req.get('techniques'):
            techniques = models.Technique.objects.filter(pk__in=[t for t in req['techniques'] if t])
        else:
            techniques = []
        ctx = {
            'shifts': req.get('shifts'),
            'facility': beamline,
            'techniques': techniques,
            'justification': req.get('justification'),
            'procedure': req.get('procedure'),
            'config': config
        }
        out_ctx['facilities'].append(ctx)
    return out_ctx


@register.inclusion_tag("proposals/facility-procs.html", takes_context=True)
def show_facility_procedures(context, reqs):
    out_ctx = {'facilities': []}
    for req in reqs:
        beamline = None
        if req.get('facility'):
            beamline = models.Facility.objects.get(pk=req['facility'])
        if req.get('techniques'):
            techniques = models.Technique.objects.filter(pk__in=[t for t in req['techniques'] if t])
        else:
            techniques = []
        ctx = {
            'shifts': req.get('shifts'),
            'facility': beamline,
            'techniques': techniques,
            'procedure': req.get('procedure')
        }
        out_ctx['facilities'].append(ctx)
    return out_ctx


@register.simple_tag(takes_context=True)
def reviewer_workload(context):
    cycle = context['cycle']
    reviewer = context['reviewer']
    return reviewer.reviews().filter(cycle=cycle).count()


@register.simple_tag(takes_context=True)
def reviewer_reviews(context):
    cycle = context['cycle']
    reviewer = context['reviewer']
    return reviewer.reviews().filter(cycle=cycle)


@register.simple_tag(takes_context=True)
def update_review_data(context):
    data = context['data']
    if isinstance(data, dict) and data.get('review'):
        review = models.Review.objects.filter(pk=data.get('review')).first()
        if review:
            context['data'] = {
                'review': review.pk,
                'spec': review.spec.form_type.code,
                'reviewer': '' if not review.reviewer else review.reviewer
            }
    return ""


@register.filter(name="get_technique")
def get_technique(pk):
    return models.Technique.objects.get(pk=pk)


@register.filter(name="color_scale")
def color_scale(val):
    return _color_scale(val)


@register.simple_tag(takes_context=True)
def get_reviewers(context, role):
    return User.objects.all_with_roles(role)


@register.simple_tag(takes_context=True)
def get_all_tracks(context):
    return models.ReviewTrack.objects.all().order_by('acronym')


@register.simple_tag(takes_context=True)
def get_technique_options(context, settings):
    if not settings:
        settings = {}
    groups = {}
    for group in sorted(models.Technique.TYPES, reverse=True):
        groups[group[-1]] = [
            (technique, settings.get(technique.pk, ""))
            for technique in models.Technique.objects.filter(category=group[0]).order_by('name')
        ]
    return groups
