from django import template
from django.db.models import Q, Count
from datetime import datetime, timedelta
from calendar import timegm
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
    ReviewCycle.STATES.pending: 'text-info-light',
    ReviewCycle.STATES.open: 'text-info',
    ReviewCycle.STATES.review: 'text-warning',
    ReviewCycle.STATES.schedule: 'text-primary',
    ReviewCycle.STATES.active: "text-success",
    ReviewCycle.STATES.archive: "text-muted",
}


@register.filter(name="state_style")
def state_style(state):
    return CYCLE_STATE_STYLES.get(state, '')


@register.filter(name="state_display")
def state_display(state):
    return models.ReviewCycle.STATES[state]


@register.inclusion_tag('proposals/cycle_track.html', takes_context=True)
def show_track(context, track, info):
    return {
        'admin': context.get('admin'),
        'owner': context.get('owner'),
        'cycle': context.get('object'),
        'cycle_state': context.get('cycle_state'),
        'track': track,
        'info': info,
    }


@register.filter(name="review_count")
def review_count(reviewer, cycle):
    return reviewer.committee_proposals(cycle).count()


@register.filter(name="review_compat")
def review_compat(reviewer, submission):
    if hasattr(reviewer, 'reviewer'):
        techniques = reviewer.reviewer.techniques.filter(
            pk__in=submission.techniques.values_list('technique', flat=True))
        areas = reviewer.reviewer.areas.all() & submission.proposal.areas.all()
        return "{}|{}".format(techniques.count(), areas.count())
    else:
        return "...|..."


@register.filter(name="facility_acronyms")
def facility_acronyms(beamlines):
    return ", ".join(beamlines.values_list('acronym', flat=True))


@register.inclusion_tag('proposals/track_submissions.html', takes_context=True)
def show_submissions(context, cycle, track):
    submissions = cycle.submissions.filter(track=track)
    reviewers = cycle.reviewers.exclude(
        Q(techniques__isnull=True) | Q(areas__isnull=True)
    )
    fac_ids = set(
        models.FacilityConfig.objects.active(cycle=cycle).accepting().filter(
            items__track=track).values_list('facility', flat=True).distinct()
    )
    if track.special:
        fac_ids |= set(
            cycle.submissions.filter(track=track).values_list('techniques__config__facility', flat=True).distinct()
        )
    facs = models.Facility.objects.filter(pk__in=fac_ids)
    facilities = {
        fac: submissions.filter(techniques__config__facility=fac, track=track).distinct().count()
        for fac in facs
    }
    techs = cycle.techniques().filter(items__track=track).distinct()
    techniques = {
        tech: {
            'submissions': submissions.filter(techniques__technique=tech).distinct().count(),
            'reviewers': tech.reviewers.filter(cycles=cycle).distinct().count(),
        }
        for tech in techs
    }
    info = {
        'admin': context.get('admin'),
        'owner': context.get('owner'),
        'facilities': facilities,
        'techniques': techniques,
        'cycle': cycle,
        'track': track,
        'total_submissions': submissions.count(),
        'total_facilities': facs.count(),
        'total_techniques': techs.count(),
        'total_reviewers': reviewers.count(),
    }
    return info


@register.inclusion_tag('proposals/track_reviews.html', takes_context=True)
def show_track_reviews(context, cycle, track):
    submissions = models.Submission.objects.filter(cycle=cycle, track=track)
    reviews = models.Review.objects.filter(pk__in=submissions.values_list('reviews', flat=True))

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
    if reviewer in cycle.reviewers.all():
        dt = datetime.today().date()
        return dt > cycle.open_date and dt <= cycle.close_date
    return False


@register.filter(name="active_reviews")
def active_reviews(cycle, reviewer):
    next_cycle = cycle.get_next_by_open_date()
    dt = datetime.today().date()

    qra = Q(track__special=True) & Q(cycle__start_date__lte=dt, cycle__end_date__gte=dt)
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
    if isinstance(cycle, str): return ""
    if cycle.state > cycle.STATES.open:
        txt = (
            "<span class='text-danger'>The submission deadline for the selected period elapsed on "
            "<em>{close_date}</em>. Submissions for General User Access will be considered for discretionary time only,"
            "until the next call for proposals, at which time you must resubmit to be considered for additional beam time. </span>"
        )
    elif cycle.state == cycle.STATES.open:
        txt = (
            "<span class='text-info'>The call for proposals to be scheduled during the selected period will close"
            "on <em>{close_date}</em>. Note that the earliest beam time for the selected "
            "scheduling period is in {start_duration}.</span>"
        )
    else:
        txt = (
            "<span class='text-muted'>The call for proposals to be scheduled during the selected period "
            "will open in {open_duration} on <em>{open_date}</em>. The list of available techniques and beamlines "
            "may change before that date. Note that the earliest beam time for the selected scheduling period is in {start_duration}.</span>"
        )
    out = txt.format(
        close_date=cycle.close_date.strftime("%b %d, %Y"),
        open_date=cycle.open_date.strftime("%b %d, %Y"),
        start_duration=timesince.timeuntil(cycle.start_date),
        open_duration=timesince.timeuntil(cycle.open_date))
    return mark_safe(out)
