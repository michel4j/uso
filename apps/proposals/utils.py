import functools
import itertools
import operator
from collections import defaultdict
from datetime import date, timedelta, datetime

from django.db.models import Case, When, BooleanField, Value, Q, Sum, IntegerField
from django.utils.safestring import mark_safe
from fuzzywuzzy import fuzz
from model_utils import Choices
from django.conf import settings

OPEN_WEEKDAY = 2  # Day of week to open call (2 = Wednesday)
CLOSE_WEEKDAY = 2  # Day of week to close call (2 = Wednesday)
ALLOC_OFFSET_WEEKS = 2  # When must all committee evaluations be completed, 2 weeks after due_date
DUE_WEEKS = 6  # Number of weeks from close of call to reviews due date
ASSIGNMENT_METHODS = getattr(settings, "USO_REVIEW_ASSIGNMENT", "BRUTE_FORCE")


def truncated_title(title, obj=None):
    return mark_safe(f'<span class="overflow ellipsis" style="max-width: 250px;"'
                     f' data-placement="bottom" title="{title}">{title}</span>')


def conv_score(num, default=0.0, converter=float):
    try:
        out = converter(num)
    except (ValueError, TypeError):
        out = default
    return out


def isodate(year, week, day):
    """Return the date for a given day on a given week of a given year.
    For example year_week_day(2015, 5, 2) should return the date corresponding
    to the wednesday of week #5 in 2015
    """
    d = date(year, 1, 4)  # Jan 4th is always in week 1
    return d + timedelta(weeks=(week - 1), days=(day - d.weekday()))


def create_cycle(today=None):
    from proposals import models
    from scheduler.models import Schedule, ShiftConfig
    log = []
    if not today:
        today = date.today()

    if today.month > 6:
        start_date = date(today.year + 1, 1, 1)
        end_date = date(today.year + 1, 7, 1)
        open_year = today.year
        open_week = 31
    else:
        start_date = date(today.year, 7, 1)
        end_date = date(today.year + 1, 1, 1)
        open_year = today.year
        open_week = 5

    open_date = isodate(open_year, open_week, OPEN_WEEKDAY)
    close_date = isodate(open_year, open_week + 4, CLOSE_WEEKDAY)
    due_date = close_date + timedelta(weeks=DUE_WEEKS)
    alloc_date = due_date + timedelta(weeks=ALLOC_OFFSET_WEEKS)
    existing = models.ReviewCycle.objects.filter(start_date=start_date, open_date=open_date)
    if not existing.count():
        description = "{}-{} {}: Schedule".format(
            start_date.strftime('%b'),
            end_date.strftime('%b'),
            end_date.strftime('%Y'),
        )
        config = ShiftConfig.objects.first()
        schedule = Schedule.objects.create(
            start_date=start_date, end_date=end_date, description=description, config=config
        )
        last_cycle = models.ReviewCycle.objects.filter(start_date__lt=start_date,
                                                       kind=models.ReviewCycle.TYPES.normal).order_by(
            'start_date').last()
        next_pk = 1 if not last_cycle else last_cycle.pk + 1
        cycle = models.ReviewCycle.objects.create(
            pk=next_pk,
            schedule=schedule,
            start_date=start_date,
            end_date=end_date,
            open_date=open_date,
            close_date=close_date,
            due_date=due_date,
            alloc_date=alloc_date
        )
        log.append('Review Cycle {0} missing, created.'.format(cycle))
    else:
        log.append('Review Cycle {0} already exists, skipping.'.format(existing[0]))
    return '\n'.join(log)


def create_mock(start_date, end_date, open_date, close_date, due_date, alloc_date):
    from proposals import models
    from scheduler.models import Schedule, ShiftConfig

    existing = models.ReviewCycle.objects.filter(start_date=start_date, open_date=open_date)
    if not existing.count():
        description = "{}-{} {}: Schedule".format(
            start_date.strftime('%b'),
            end_date.strftime('%b'),
            end_date.strftime('%Y'),
        )
        config = ShiftConfig.objects.latest('created')
        schedule = Schedule.objects.create(
            start_date=start_date, end_date=end_date, description=description, config=config
        )
        last_cycle = models.ReviewCycle.objects.filter(start_date__lt=start_date,
                                                       kind=models.ReviewCycle.TYPES.mock).order_by('start_date').last()
        next_pk = 9991 if not last_cycle else last_cycle.pk + 1
        models.ReviewCycle.objects.create(
            pk=next_pk,
            kind=models.ReviewCycle.TYPES.mock,
            schedule=schedule,
            start_date=start_date,
            end_date=end_date,
            open_date=open_date,
            close_date=close_date,
            due_date=due_date,
            alloc_date=alloc_date
        )


def check_conflict(user, proposal):
    # exclude matching emails
    emails = {email.lower() for email in [_f for _f in [user.email, user.alt_email] if _f]}
    proposal_emails = {email.lower() for email in proposal.proposal.team}
    if emails & proposal_emails:
        return 1

    # exclude matching names
    user_name = user.get_full_name().strip().lower()
    proposal_names = {
                         " ".join([t.get('first_name', ''), t.get('last_name', '')]).strip().lower()
                         for t in proposal.proposal.get_full_team()
                     } | {
                         " ".join([i.get('first_name', ''), i.get('last_name', ''),
                                   i.get('other_names', '')]).strip().lower()
                         for i in proposal.proposal.details.get('inappropriate_reviewers', [])
                     }
    for name in proposal_names:
        if fuzz.ratio(name, user_name) > 90: return 1
        if fuzz.token_sort_ratio(name, user_name) > 90: return 1
    return 0


def assign_cmacra_old(cycle, track):
    """ Generate input for CMACRA"""
    from proposals import models
    revs = cycle.reviewers.filter(committee__isnull=True).exclude(techniques__isnull=True).order_by('?').distinct()
    props = cycle.submissions.exclude(techniques__isnull=True).filter(track=track).distinct()
    techniques = cycle.techniques().filter(items__track=track).distinct()
    areas = models.SubjectArea.objects.filter(pk__in=props.values_list('proposal__areas', flat=True).distinct())

    num_subjects = techniques.count()
    num_proposals = props.count()
    num_reviewers = revs.count()
    num_areas = areas.count()

    rev_techs = {rev: set(rev.techniques.values_list('pk', flat=True)) for rev in revs}
    rev_areas = {rev: set(rev.areas.values_list('pk', flat=True)) for rev in revs}
    prop_techs = {prop: set(prop.techniques.values_list('technique__pk', flat=True)) for prop in props}
    prop_areas = {prop: set(prop.proposal.areas.values_list('pk', flat=True)) for prop in props}

    REVIEWERS = [[int(k.pk in rev_techs[rev]) for k in techniques] for rev in revs]
    PROPOSALS = [[int(k.pk in prop_techs[prop]) for k in techniques] for prop in props]

    REVIEWER_AREAS = [[int(a.pk in rev_areas[rev]) for a in areas] for rev in revs]
    PROPOSAL_AREAS = [[int(a.pk in prop_areas[prop]) for a in areas] for prop in props]

    CONFLICTS = [[check_conflict(rev.user, prop) for rev in revs] for prop in props]

    from ortools.linear_solver import pywraplp
    num_reviews = track.min_reviewers  # Min proposal coverage (reviews/proposal)
    max_workload = track.max_proposals  # Max reviewer workload

    # Init Solver
    solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.GLOP_LINEAR_PROGRAMMING)
    # solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.CLP_LINEAR_PROGRAMMING)

    X = [[solver.IntVar(0, 1, "M[{},{}]".format(i, j)) for j in range(num_reviewers)] for i in range(num_proposals)]
    t = [
        [solver.IntVar(0, num_reviews, "t[{},{}]".format(i, j))
         for j in range(num_subjects)] for i in range(num_proposals)
    ]
    score = solver.Sum([v for Vs in t for v in Vs])

    # Constraints
    # Proposal Coverage constraints
    for i in range(num_proposals):
        solver.Add(solver.Sum([X[i][j] for j in range(num_reviewers)]) == num_reviews)  # coverage equal to num_reviews

    # Reviewer workload constraints
    for j in range(num_reviewers):
        solver.Add(solver.Sum([X[i][j] for i in range(num_proposals)]) <= max_workload)

    # Technique Match constraints
    for i in range(num_proposals):
        for j in range(num_subjects):
            solver.Add(
                solver.Sum([REVIEWERS[l][j] * X[i][l] for l in range(num_reviewers)]) >= PROPOSALS[i][j] * t[i][j])

    # Conflict of Interests/subject area constraints
    for i in range(num_proposals):
        for j in range(num_reviewers):
            if CONFLICTS[i][j]:
                solver.Add(X[i][j] == 0)
            else:
                # subject areas
                solver.Add(
                    solver.Sum([PROPOSAL_AREAS[i][m] * REVIEWER_AREAS[j][m] for m in range(num_areas)]) >= X[i][j]
                )

    # solution and search
    solver.Maximize(score)
    status = solver.Solve()

    conflicts = {props[i]: [revs[j].user for j in range(num_reviewers) if CONFLICTS[i][j]] for i in
                 range(num_proposals)}
    prop_results = {props[i]: [revs[j].user for j in range(num_reviewers) if X[i][j].SolutionValue()] for i in
                    range(num_proposals)}
    revs_results = {revs[j].user: [props[i] for i in range(num_proposals) if X[i][j].SolutionValue()] for j in
                    range(num_reviewers)}

    print("Objective : %0.2f" % solver.Objective().Value())
    print("Duration  :", solver.WallTime(), "ms")
    if status == solver.OPTIMAL:
        success = 'optimal'
    elif status == solver.FEASIBLE:
        success = 'feasible'
    else:
        success = False

    return prop_results, revs_results, conflicts, success


def cmacra_optimize(proposals, reviewers, techniques, areas, minimum=1, maximum=4):
    from ortools.linear_solver import pywraplp

    # Init Solver
    solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.GLOP_LINEAR_PROGRAMMING)
    # solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.CLP_LINEAR_PROGRAMMING)
    # solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
    # solver = pywraplp.Solver("CMACRASolver", pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

    subjects = [subj for subj in itertools.chain(techniques, areas)]

    num_techniques = techniques.count()
    num_areas = areas.count()
    num_proposals = proposals.count()
    num_reviewers = reviewers.count()
    num_subjects = len(subjects)

    rev_subjects = {
        rev: set(itertools.chain(rev.techniques.all(), rev.areas.all()))
        for rev in reviewers
    }
    pro_subjects = {
        prop: set(itertools.chain(prop.techniques.all(), prop.proposal.areas.all()))
        for prop in proposals
    }

    rev_techniques = {
        rev: set(rev.techniques.all())
        for rev in reviewers
    }
    pro_techniques = {
        prop: set(prop.techniques.all())
        for prop in proposals
    }
    rev_areas = {
        rev: set(rev.techniques.all())
        for rev in reviewers
    }
    pro_areas = {
        prop: set(prop.proposal.areas.all())
        for prop in proposals
    }

    rev_tech_mat = [[int(subj in rev_techniques[rev]) for subj in techniques] for rev in reviewers]
    pro_tech_mat = [[int(subj in pro_techniques[pro]) for subj in techniques] for pro in proposals]
    rev_area_mat = [[int(subj in rev_areas[rev]) for subj in areas] for rev in reviewers]
    pro_area_mat = [[int(subj in pro_areas[pro]) for subj in areas] for pro in proposals]

    conflict_mat = [[check_conflict(rev.user, pro) for rev in reviewers] for pro in proposals]

    rev_subj_mat = [[int(subj in rev_subjects[rev]) for subj in subjects] for rev in reviewers]
    pro_subj_mat = [[int(subj in pro_subjects[pro]) for subj in subjects] for pro in proposals]

    M = {
        (i, l): solver.IntVar(0, 1, "M[{},{}]".format(i, l))
        for l in range(num_reviewers) for i in range(num_proposals)
    }
    t = {
        (i, j): solver.IntVar(0, minimum, "t[{},{}]".format(i, j))
        for j in range(num_subjects) for i in range(num_proposals)
    }

    # Constraints
    # Subject Match constraints
    for i in range(num_proposals):
        for j in range(num_subjects):
            solver.Add(
                solver.Sum(
                    [rev_subj_mat[l][j] * M[i, l] for l in range(num_reviewers)]
                ) >= pro_subj_mat[i][j] * t[i, j]
            )
            solver.Add(
                t[i, j] == solver.Sum(
                    [M[i, l] * pro_subj_mat[i][j] * rev_subj_mat[l][j] for l in range(num_reviewers)]
                )
            )

    # Proposal Coverage constraints
    # coverage equal to minimum
    for i in range(num_proposals):
        solver.Add(
            solver.Sum(
                [M[i, l] for l in range(num_reviewers)]
            ) == minimum
        )

    # Reviewer workload and conflicts constraints
    for l in range(num_reviewers):
        solver.Add(
            solver.Sum(
                [M[i, l] for i in range(num_proposals)]
            ) <= maximum
        )
        solver.Add(
            solver.Sum(
                [M[i, l] * conflict_mat[i][l] for i in range(num_proposals)]
            ) == 0
        )

    # solution and search
    score = solver.Sum(list(t.values()))
    solver.Maximize(score)
    status = solver.Solve()

    for i in range(num_proposals):
        for j in range(num_subjects):
            print(int(t[i, j].SolutionValue()), end=' ')
        print()

    conflicts = {
        prop: [rev for j, rev in enumerate(reviewers) if conflict_mat[i][j]]
        for i, prop in enumerate(proposals)
    }
    prop_results = {
        prop: [rev for j, rev in enumerate(reviewers) if M[i, j].SolutionValue()]
        for i, prop in enumerate(proposals)
    }
    revs_results = {
        rev: [prop for i, prop in enumerate(proposals) if M[i, j].SolutionValue()]
        for j, rev in enumerate(reviewers)
    }
    return prop_results, revs_results, conflicts, solver, status


def assign_cmacra(cycle, track):
    """ Assign Reviewers to Proposals using CMACRA"""
    from proposals import models
    reviewers = cycle.reviewers.filter(committee__isnull=True).exclude(techniques__isnull=True).order_by('?').distinct()
    proposals = cycle.submissions.exclude(techniques__isnull=True).filter(track=track).distinct()
    techniques = models.Technique.objects.filter(
        pk__in=cycle.submissions.filter(track=track).values_list('techniques__technique', flat=True)).distinct()
    areas = models.SubjectArea.objects.filter(pk__in=proposals.values_list('proposal__areas', flat=True).distinct())
    prop_results, revs_results, conflicts, solver, status = cmacra_optimize(
        proposals, reviewers, techniques, areas, track.min_reviewers, track.max_proposals
    )

    if status == solver.OPTIMAL:
        success = 'optimal'
    elif status == solver.FEASIBLE:
        success = 'feasible'
    else:
        success = False

    print("Objective : %0.2f" % solver.Objective().Value())
    print("Duration  :", solver.WallTime(), "ms", success)
    return prop_results, revs_results, conflicts, success


def assign_prc(cycle, track):
    """ Generate input for CMACRA"""
    from proposals import models
    reviewers = track.committee.all()
    proposals = cycle.submissions.exclude(techniques__isnull=True).filter(track=track).distinct()
    techniques = cycle.techniques().filter(items__track=track).distinct()
    areas = models.SubjectArea.objects.filter(pk__in=proposals.values_list('proposal__areas', flat=True).distinct())

    minimum = 1  # Min proposal coverage (reviews/proposal)
    maximum = 2 + proposals.count() // max(1, reviewers.count())  # Max reviewer workload

    prop_results, revs_results, conflicts, solver, status = cmacra_optimize(
        proposals, reviewers, techniques, areas, minimum, maximum
    )

    if status == solver.OPTIMAL:
        success = 'optimal'
    elif status == solver.FEASIBLE:
        success = 'feasible'
    else:
        success = False

    print("Objective : %0.2f" % solver.Objective().Value())
    print("Duration  :", solver.WallTime(), "ms", success)
    return prop_results, revs_results, conflicts, success


def assign_brute_force(cycle, track):
    """ Assign Reviewers to Proposals using BRUTE_FORCE"""
    assignments = defaultdict(set)
    submissions = cycle.submissions.exclude(techniques__isnull=True).filter(track=track).distinct()
    for submission in submissions.order_by('?'):
        technique_ids = [t.technique.pk for t in submission.techniques.all()]
        area_ids = [a.pk for a in submission.proposal.areas.all()]
        techniques_filter = functools.reduce(operator.__or__, [Q(techniques__pk=t) for t in technique_ids])
        areas_filter = functools.reduce(operator.__or__, [Q(areas=a) for a in area_ids], Q())

        cycle_reviewers = cycle.reviewers.filter(areas_filter)
        cycle_reviewers = cycle_reviewers.filter(techniques_filter)
        cycle_reviewers = cycle_reviewers.distinct().annotate(
            num_reviews=Sum(
                Case(
                    When(Q(user__reviews__cycle=cycle), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ),
        )
        prc_reviewers = cycle_reviewers.filter(committee=track)
        matched_reviewers = cycle_reviewers.filter(num_reviews__lt=track.max_proposals)

        candidates = [
            rev.pk for rev in matched_reviewers.exclude(committee=track).all()
            if check_conflict(rev.user, submission) == 0
        ]

        queryset = cycle.reviewers.filter(Q(pk__in=candidates)).order_by('?')

        if queryset.count() > track.min_reviewers:
            assignments[submission] |= set(queryset[:track.min_reviewers])
        else:
            assignments[submission] |= set(queryset.all())

        if not prc_reviewers.count(): continue

        if track.max_proposals == 0:
            assignments[submission] |= set(cycle.reviewers.filter(committee=track))
        else:
            prc_quota = (1 + submissions.count() // prc_reviewers.count())
            prc_candidates = prc_reviewers.filter(num_reviews__lt=prc_quota)
            prc = prc_candidates.order_by('?').first()
            if prc:
                assignments[submission].add(prc)

    return assignments, {}, {}, 'optimal'


def assign_reviewers(cycle, track):
    if ASSIGNMENT_METHODS == "CMACRA":
        return assign_cmacra(cycle, track)
    else:
        return assign_brute_force(cycle, track)


def _create_submissions(proposal):
    from . import models
    reqs = proposal.details['beamline_reqs']
    cycle = models.ReviewCycle.objects.get(pk=proposal.details['first_cycle'])
    effective_date = cycle.start_date

    fcs = []
    for req in reqs:
        fc = models.FacilityConfig.objects.active(effective_date).filter(facility__pk=req.get('facility')).last()
        if fc:
            fcs.append((fc, fc.items.filter(technique__kind__pk__in=req.get('techniques', []))))
    info = {
        "requests": fcs,
        "cycle": cycle,
    }

    cycle = info["cycle"]
    tracks = defaultdict(list)
    special_track = models.ReviewTrack.objects.get(special=True)

    SPECIAL = ['maintenance', 'staff', 'staff-commissioning', 'beamteam',
               'beamteam-commissioning', 'purchased', 'user-special', 'usr-commissioning']

    for fc in info["requests"]:
        if proposal.details.get('proposal_type', 'user') in SPECIAL:
            tracks[special_track].append(fc[1].operating())
        else:
            track = models.ReviewTrack.objects.exclude(special=True).filter(
                pk__in=fc[1].operating().values_list('technique__track', flat=True).distinct()).first()
            if track:
                tracks[track].append(fc[1].operating())
        if fc[1].commissioning().count():
            tracks[special_track].append(fc[1].commissioning())

    from dynforms.models import FormType
    tech_form = FormType.objects.all().filter(code='technical-review')
    to_create = []
    for track, fcs in list(tracks.items()):
        obj, created = models.Submission.objects.get_or_create(
            proposal=proposal,
            track=track,
            cycle=cycle)
        items = [v for v in itertools.chain(*fcs)]
        technical_roles = {'beamline-admin:{}'.format(i.config.facility.acronym.lower()) for i in items}
        obj.techniques.add(*items)
        obj.save()

        to_create.extend([
            models.Review(role=r, proposal=obj, kind=models.Review.TYPES.technical, spec=tech_form)
            for r in technical_roles
        ])

    # create review objects for technical
    models.Review.objects.bulk_create(to_create)

    proposal.state = proposal.STATES.submitted
    proposal.save()


DECISIONS = Choices(
    (0, 'exempt', 'Exempt'),
    (1, 'protocol', 'Protocol'),
    (2, 'ethics', 'Ethics'),
    (3, 'rejected', 'Rejected'),
)


def combine_ethics_reviews(info, existing):
    new_info = {}
    new_info.update(existing)
    sample = int(info['sample'])
    decision = info['decision']
    if 'decision' in existing:
        decision = sorted([decision, existing.get('decision', 0)], key=lambda x: getattr(DECISIONS, x, 0))[-1]
    new_info.update(sample=sample, decision=decision)

    if info.get('expiry'):
        expiry = datetime.strptime(info['expiry'], '%Y-%m-%d').date()
        if existing.get('expiry'):
            expiry = min(expiry, existing['expiry'])
        new_info.update(expiry=expiry)

    return new_info


def _color_scale(val, lo=1, hi=5, max_saturation=180):
    if not isinstance(val, float):
        return ''
    n = int(min(255, max(0, (val - lo) * max_saturation // (hi - lo))))
    return '#%02x%02x%02x' % (n, max_saturation - n, 0)


def score_format(val, obj=None):
    if val:
        return mark_safe(f"<span style='font-weight: bold; color: {_color_scale(val, 1, 5)};'>{val:.2f}</span>")
    else:
        return "&hellip;"


def stdev_format(val, obj=None):
    if val:
        return mark_safe(f"<span style='font-weight: bold; color: {_color_scale(val, 0.1, 3)};'>{val:.2f}</span>")
    else:
        return mark_safe("&hellip;")


def get_techniques_matrix(cycle=None, sel_techs=(), sel_fac=None):
    """Generate a dictionary mapping each technique to a list of available facilities and
    each facility to a list available techniques. Entries in the lists are tuples of the form
    (primary_key, unicode label, bool selected). The selected field will be true if the primary key was passed in
    the sel_techs or sel_fac.
    """
    from proposals import models
    tech_facs = defaultdict(list)
    fac_techs = defaultdict(list)

    if not cycle:
        return {'techniques': [], 'facilities': []}

    if not sel_techs:
        sel_techs = [0]

    for conf in models.FacilityConfig.objects.active(cycle=cycle.pk).accepting():
        for t in conf.items.values_list('technique', flat=True):
            tech_facs[t].append(conf.facility.pk)
            fac_techs[conf.facility.pk].append(t)

    techs = models.Technique.objects.filter(pk__in=list(tech_facs.keys())).annotate(
        selected=Case(
            When(pk__in=sel_techs, then=Value(1)),
            default=Value(0), output_field=BooleanField()
        )
    ).order_by('name')

    facs = models.Facility.objects.filter(pk__in=list(fac_techs.keys())).annotate(
        selected=Case(
            When(pk=sel_fac, then=Value(1)),
            default=Value(0), output_field=BooleanField()
        )
    ).order_by('name')
    matrix = {
        'techniques': [
            (t.pk, str(t), t.selected, tech_facs[t.pk])
            for t in techs
        ],
        'facilities': [
            (f.pk, str(f), f.selected, fac_techs[f.pk])
            for f in facs
        ]
    }
    return matrix
