from django import template
from django.db.models import Q, Count, Avg, StdDev, F, Max, Value
from datetime import datetime, timedelta
from calendar import timegm

from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from proposals import models
from publications import stats
from collections import defaultdict
import numpy
from django.utils.safestring import mark_safe
from django.utils import timezone, timesince

register = template.Library()

from proposals.models import ReviewCycle

CYCLE_STATE_STYLES = {
    ReviewCycle.STATES.pending: 'text-info-emphasis',
    ReviewCycle.STATES.open: 'text-info',
    ReviewCycle.STATES.review: 'text-warning',
    ReviewCycle.STATES.schedule: 'text-primary',
    ReviewCycle.STATES.active: "text-success",
    ReviewCycle.STATES.archive: "text-body-secondary",
}


@register.filter(name="state_style")
def state_style(state):
    return CYCLE_STATE_STYLES.get(state, '')


@register.filter(name="state_display")
def state_display(state):
    return models.ReviewCycle.STATES[state]


@register.filter(name="for_stage")
def for_stage(queryset, stage):
    return queryset.filter(stage=stage).order_by('reviewer__reviewer__committee')


@register.inclusion_tag('proposals/cycle-track.html', takes_context=True)
def show_track(context, track):
    return {
        'admin': context.get('admin'),
        'owner': context.get('owner'),
        'cycle': context.get('object'),
        'cycle_state': context.get('cycle_state'),
        'track': track,
    }


@register.filter(name="review_count")
def review_count(reviewer, cycle):
    return reviewer.committee_proposals(cycle).count()


@register.filter(name="review_compat")
def review_compat(reviewer, submission):
    if hasattr(reviewer, 'reviewer'):
        sub_techs = set(submission.techniques.values_list('technique', flat=True))
        user_techs = set(reviewer.reviewer.techniques.values_list('pk', flat=True))
        matches = sub_techs & user_techs

        sub_areas = set(submission.proposal.areas.values_list('pk', flat=True))
        user_areas = set(reviewer.reviewer.areas.values_list('pk', flat=True))
        areas = sub_areas & user_areas

        return mark_safe(
            f"<span class='text-primary' title='Techniques'>{len(matches)}/{len(sub_techs)}</span>&nbsp;&mdash;&nbsp;"
            f"<span class='text-success' title='Fields'>{len(areas)}/{len(sub_areas)}</span>"
        )
    else:
        return mark_safe(
            f"<span class='text-primary'>&middot;</span>&nbsp;:&nbsp;"
            f"<span class='text-success'>&middot;</span>"
        )


@register.filter(name="facility_acronyms")
def facility_acronyms(beamlines):
    return ", ".join(beamlines.values_list('acronym', flat=True))


@register.inclusion_tag('proposals/track-stats.html', takes_context=True)
def show_track_stats(context, cycle, track):
    #reviewers = models.Reviewer.objects.available(cycle)
    if cycle.state < cycle.STATES.open:
        submissions = models.Submission.objects.none()
        techs = cycle.techniques().filter(items__track=track).distinct()
        facilities = cycle.configs().annotate(
            facility_acronym=F('facility__acronym')
        ).values('facility_acronym').annotate(count=Count('techniques', distinct=True))
    else:
        submissions = cycle.submissions.filter(track=track)
        facilities = cycle.submissions.filter(track=track).annotate(
            facility_acronym=F('techniques__config__facility__acronym')
        ).values('facility_acronym').annotate(count=Count('id', distinct=True))
        techs = cycle.techniques().filter(items__track=track, items__submissions__in=submissions).distinct()

    info = {
        'admin': context.get('admin'),
        'owner': context.get('owner'),
        'facilities': facilities,
        'cycle': cycle,
        'track': track,
        'total_submissions': submissions.count(),
        'total_facilities': facilities.count(),
        'total_techniques': techs.count(),
        #'total_reviewers': reviewers.count(),
    }
    return info


@register.inclusion_tag('proposals/technique-reviewer-matrix.html', takes_context=True)
def show_technique_matrix(context, cycle, track):
    techs = models.Technique.objects.filter(
        items__track=track, items__submissions__cycle=cycle
    ).annotate(
        num_proposals=Count('items__submissions', distinct=True),
        num_reviewers=Count('reviewers', distinct=True)
    ).annotate(
        redundancy=F('num_reviewers') / F('num_proposals')
    ).values(
        'name', 'acronym', 'num_proposals', 'num_reviewers', 'redundancy'
    ).order_by('redundancy')

    techniques = {
        t["acronym"]: {
            'name': t['name'],
            'submissions': t['num_proposals'],
            'reviewers': t['num_reviewers'],
            'redundancy': t['redundancy'] * 100,
        } for t in techs[:20]
    }
    info = {
        'admin': context.get('admin'),
        'owner': context.get('owner'),
        'techniques': techniques,
        'cycle': cycle,
        'track': track,
    }
    return info


@register.inclusion_tag('proposals/track-committee.html', takes_context=True)
def show_track_committee(context, cycle, track):
    reviews = models.Review.objects.filter(cycle=cycle, stage__track=track).distinct()

    info = []
    rev_list = [('Technical', reviews.technical(), 'info'), ('Scientific', reviews.scientific(), 'success')]
    for name, revs, css in rev_list:
        total = revs.count()
        reviewers = revs.values_list('reviewer').distinct().count()
        complete = revs.complete().count()
        percent = int(100.0 * complete / max(1, total))
        complete_reviewers = revs.complete().values('reviewer').distinct().count()
        if total:
            info.append({
                'name': name,
                'total': total,
                'complete': complete,
                'percent': percent,
                'reviewers': reviewers,
                'complete_reviewers': complete_reviewers,
                'css': css
            })

    return {
        'admin': context.get('admin'),
        'owner': context.get('owner'),
        'cycle_state': context.get('cycle_state'),
        'cycle': cycle,
        'track': track,
        'total_reviews': reviews.count(),
        'total_reviewers': sum([v['reviewers'] for v in info]),
        'reviews': reviews,
        'review_types': info,
    }


def accumulate(iterator):
    total = 0
    for item in iterator:
        total += item
        yield total


def summarize_response(qset):
    tracks = models.ReviewTrack.objects.all()
    props = {k.acronym: defaultdict(int) for k in tracks}

    days = list(qset.datetimes('created', 'day').distinct())
    for d, track in qset.datetimes('created', 'day').values_list('datetimefield', 'track__acronym'):
        props[track][d] += 1

    cols = ['Review Track'] + [timegm(datetime.combine(d, datetime.max.time()).utctimetuple()) * 1000 for d in days] + [
        'All']
    _tbl = [cols]
    for k, r in list(props.items()):
        vals = list(accumulate([r[d] for d in days]))
        r = [k] + vals + [sum(r.values())]
        _tbl.append(r)
    r = ['Total'] + [sum(xr[1:]) for xr in zip(*_tbl)[1:]]
    _tbl.append(r)
    data_table = stats.DataTable(_tbl)
    return data_table


def summarize_bl_response(qset):
    tracks = models.ReviewTrack.objects.all()
    field = 'techniques__config__facility__acronym'
    bls = qset.values(field).distinct()
    props = {k[field]: {'total': 0, 'multi': 0, 'track': defaultdict(int)} for k in bls}

    for submission in qset.all():
        facs = submission.techniques.all().values('config__facility__acronym').distinct()
        for fac in facs:
            k = fac['config__facility__acronym']
            props[k]['track'][submission.track.acronym] += 1
            if facs.count() > 1:
                props[k]['multi'] += 1

    tracks = [t.acronym for t in tracks]
    cols = ['Review Track'] + tracks + ['NIMBLE', 'All']
    _tbl = [cols]
    for k in bls:
        r = [props[k[field]]['track'][t] for t in tracks]
        n = [props[k[field]]['multi']]
        if k[field]:
            r = [k[field]] + r + n + [sum(r)]
            _tbl.append(r)
    r = ['Total'] + [sum(xr[1:]) for xr in zip(*_tbl)[1:]]
    rem_col = []
    for i, v in enumerate(r):
        if v == 'Total': continue
        if v > 0:
            break
        else:
            rem_col.append(i)

    _tbl.append(r)

    data_table = stats.DataTable(_tbl)
    data_table.remove_columns(rem_col)
    return data_table


@register.simple_tag
def get_current_cycle():
    return models.ReviewCycle.objects.all().active().last()


@register.simple_tag
def get_next_cycle(dt=datetime.today()):
    return models.ReviewCycle.objects.all().next(dt)


@register.filter(name="reviewer_window")
def reviewer_window(cycle, reviewer):
    potential = (
        reviewer.active and not reviewer.is_suspended(cycle.open_date)
    )
    return potential


@register.filter(name="active_reviews")
def active_reviews(cycle, reviewer):
    next_cycle = cycle.get_next_by_open_date()
    dt = datetime.today().date()

    qra = Q(track__require_call=False) & Q(cycle__start_date__lte=dt, cycle__end_date__gte=dt)
    qgu = Q(cycle__close_date__lt=dt) & Q(cycle__due_date__gte=dt) | Q(cycle__due_date__isnull=True)
    qchain = Q(proposal__in=cycle.submissions.filter(qra))
    qchain |= Q(proposal__in=next_cycle.submissions.filter(qgu))

    return models.Review.objects.filter(reviewer=reviewer).filter(qchain)


@register.filter(name="active_submissions")
def active_submissions(cycle, reviewer):
    return cycle.get_next_by_open_date().submissions.filter(reviewer=reviewer)


@register.filter(name="get_comments")
def get_comments(feedback):
    return [(k.replace('_', ' ').replace("comments", ""), v) for k, v in list(feedback.details.items()) if
            v and 'comment' in k]


@register.filter(name="cycle_comments", autoescape=True)
def cycle_comments(cycle):
    if isinstance(cycle, str) or cycle is None:
        return ""
    if cycle.state > cycle.STATES.open:
        txt = (
            "<span class='text-danger'>The call for proposals closed on "
            "<em>{close_date}</em>.</span>"
        )
    elif cycle.state == cycle.STATES.open:
        txt = (
            "<span class='text-info'>The call for proposals will close on <em>{close_date}</em>.</span>"
        )
    else:
        txt = (
            "<span class='text-body-secondary'>The call for proposals will open in {open_duration} "
            "on <em>{open_date}</em>.</span>"
        )
    out = txt.format(
        close_date=cycle.close_date.strftime("%b %d, %Y"),
        open_date=cycle.open_date.strftime("%b %d, %Y"),
        start_duration=timesince.timeuntil(cycle.start_date),
        open_duration=timesince.timeuntil(cycle.open_date))
    return mark_safe(out)


@register.inclusion_tag('proposals/stage-stats.html')
def stage_stats(stage, cycle):
    info = stage.reviews.filter(cycle=cycle).aggregate(
        avg_score=Coalesce(Avg('score', filter=Q(state__gte=models.Review.STATES.submitted)), Value(0.0)),
        std_dev=Coalesce(StdDev('score', filter=Q(state__gte=models.Review.STATES.submitted)), Value(0.0)),
        total=Count('id'),
        completed=Count('id', filter=Q(state__gte=models.Review.STATES.submitted)),
    )
    percentage = 100 * info['completed'] / max(1, info['total'])
    return {
        'entries': [
            {
                'description': "Reviews",
                'value': f"{info['total']}",
                'units': "REV",
            },
            {
                'description': "Completed",
                'value': f"{percentage:0.1f}",
                'units': "%",
            },
            {
                'description': mark_safe("Avg&nbsp;Score"),
                'value': f"{info['avg_score']:0.1f}",
                'units': "",
            }
        ]
    }