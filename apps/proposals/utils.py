import functools
import itertools
import operator
from collections import defaultdict
from datetime import date, timedelta, datetime
from typing import Literal

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Case, When, BooleanField, Value, Q, Sum, IntegerField
from django.utils.safestring import mark_safe
from fuzzywuzzy import fuzz
from model_utils import Choices

OPEN_WEEKDAY = 2  # Day of week to open call (2 = Wednesday)
CLOSE_WEEKDAY = 2  # Day of week to close call (2 = Wednesday)
ALLOC_OFFSET_WEEKS = 2  # When must all committee evaluations be completed, 2 weeks after due_date
DUE_WEEKS = 6  # Number of weeks from close of call to reviews due date

USO_REVIEW_ASSIGNMENT = getattr(settings, "USO_REVIEW_ASSIGNMENT", "BRUTE_FORCE")
USO_TECHNICAL_REVIEWS = getattr(settings, "USO_TECHNICAL_REVIEWS", [])
USO_SCIENCE_REVIEWS = getattr(settings, "USO_SCIENCE_REVIEWS", [])
USO_SAFETY_REVIEWS = getattr(settings, "USO_SAFETY_REVIEWS", [])
USO_SAFETY_APPROVAL = getattr(settings, "USO_SAFETY_APPROVAL", "approval")


def truncated_title(title, obj=None):
    return mark_safe(
        f'<span class="overflow ellipsis" style="max-width: 250px;"'
        f' data-placement="bottom" title="{title}">{title}</span>'
    )


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
        description = f"{start_date.strftime('%b')}-{end_date.strftime('%b')} {end_date.strftime('%Y')}: Schedule"
        config = ShiftConfig.objects.first()
        schedule = Schedule.objects.create(
            start_date=start_date, end_date=end_date, description=description, config=config
        )
        last_cycle = models.ReviewCycle.objects.filter(
            start_date__lt=start_date,
            kind=models.ReviewCycle.TYPES.normal
        ).order_by(
            'start_date'
        ).last()
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
        log.append(f'Review Cycle {cycle} missing, created.')
    else:
        log.append(f'Review Cycle {existing[0]} already exists, skipping.')
    return '\n'.join(log)


def create_mock(start_date, end_date, open_date, close_date, due_date, alloc_date):
    from proposals import models
    from scheduler.models import Schedule, ShiftConfig

    existing = models.ReviewCycle.objects.filter(start_date=start_date, open_date=open_date)
    if not existing.count():
        description = f"{start_date.strftime('%b')}-{end_date.strftime('%b')} {end_date.strftime('%Y')}: Schedule"
        config = ShiftConfig.objects.latest('created')
        schedule = Schedule.objects.create(
            start_date=start_date, end_date=end_date, description=description, config=config
        )
        last_cycle = models.ReviewCycle.objects.filter(
            start_date__lt=start_date,
            kind=models.ReviewCycle.TYPES.mock
        ).order_by('start_date').last()
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


def get_submission_info(submission):
    """
    Get submission information for matching
    :param submission: submission
    :return: dictionary
    """
    proposal = submission.proposal
    return {
        'techniques': set(submission.techniques.values_list('technique__pk', flat=True)),
        'areas': set(proposal.areas.values_list('pk', flat=True)),
        'emails': {user.get('email', '') for user in proposal.get_full_team()},
        'conflicts': {
            f'{r["fist_name"]},{r["last_name"]}'.strip().lower()
            for r in proposal.details.get('inappropriate_reviewers', [])
        }
    }


def get_reviewer_info(reviewer):
    """
    Get reviewer information for matching
    :param reviewer: reviewer
    :return: dictionary
    """
    return {
        'techniques': set(reviewer.techniques.values_list('pk', flat=True)),
        'areas': set(reviewer.areas.filter(category__isnull=True).values_list('pk', flat=True)),
        'emails': {
            email.strip().lower() for email in [_f for _f in [reviewer.user.email, reviewer.user.alt_email] if _f]
        },
        'name': f'{reviewer.user.first_name},{reviewer.user.last_name}'.strip().lower()
    }


def is_incompatible(proposal, reviewer, committee=False) -> Literal[0, 1]:
    """
    Check if a reviewer is incompatible with a submission
    :param proposal: proposal information dictionary
    :param reviewer: reviewer information dictionary
    :param committee: flag to indicate committee review
    :return: 0 if compatible, 1 if incompatible
    """
    return max(
        veto_conflict(proposal, reviewer),
        veto_technique(proposal, reviewer, committee),
        veto_subject(proposal, reviewer)
    )


def has_conflict(proposal, reviewer) -> Literal[0, 1]:
    """
    Check if a reviewer has a conflict with a submission
    :param proposal: proposal information dictionary
    :param reviewer: reviewer information dictionary
    """
    p_info = get_submission_info(proposal)
    r_info = get_reviewer_info(reviewer)
    return veto_conflict(p_info, r_info)


def veto_conflict(proposal: dict, reviewer: dict, lax: bool = False) -> Literal[0, 1]:
    """
    Check if a reviewer is incompatible with a submission based on emails and names
    :param proposal: proposal information
    :param reviewer: reviewer information
    :param lax: ignore this check
    :return: 0 or 1
    """

    if lax:
        return 0
    return 1 if any((
        proposal['emails'] & reviewer['emails'],
        reviewer['name'] in proposal['conflicts'],
    )) else 0


def veto_technique(proposal: dict, reviewer: dict, lax: bool = False) -> Literal[0, 1]:
    """
    Check if a reviewer is incompatible with a submission based on techniques
    :param proposal: proposal information
    :param reviewer: reviewer information
    :param lax: ignore this check
    :return: 0 or 1
    """
    if lax:
        return 0
    return 0 if len(proposal['techniques'] & reviewer['techniques']) else 1


def veto_subject(proposal: dict, reviewer: dict, lax: bool = False) -> Literal[0, 1]:
    """
    Check if a reviewer is incompatible with a submission based on subject areas
    :param proposal: proposal information
    :param reviewer: reviewer information
    :param lax: ignore this check
    :return: 0 or 1
    """
    if lax:
        return 0
    return 0 if len(proposal['areas'] & reviewer['areas']) else 1


def reward_cost(proposal, reviewer) -> float:
    """
    Calculate the reward cost for a proposal-reviewer pair
    :param proposal: proposal
    :param reviewer: reviewer
    :return: reward
    """
    reward = 10
    # reward for matching technique
    reward *= len(proposal['techniques'] & reviewer['techniques'])
    reward *= len(proposal['areas'] & reviewer['areas'])
    return reward


def penalty_cost(proposal, reviewer):
    """
    Calculate the penalty cost for a proposal-reviewer pair
    :param proposal: proposal
    :param reviewer: reviewer
    :return: penalty
    """
    cost = 100
    # reward for matching technique
    scale = len(proposal['techniques'] & reviewer['techniques'])
    scale *= len(proposal['areas'] & reviewer['areas'])
    cost = max(0, cost - scale * 10)
    return cost


def mip_optimize(proposals, reviewers, min_assignment=1, max_workload=4, committee=False, method='SCIP'):
    """
    Given a set of submissions and reviewers, assign reviewers
    :param proposals: submissions queryset
    :param reviewers: reviewers queryset
    :param cycle: review cycle
    :param min_assignment: minimum number of reviews to assign
    :param max_workload: maximum workload for each reviewer
    :param committee: whether this is a committee assignment or now
    :param method: solver method, one of 'SCIP', 'CLP', 'GLOP'
    :return: assignments dictionary mapping submission to a set of reviewers
    """

    from ortools.linear_solver import pywraplp

    proposal_list = list(proposals)
    reviewer_list = list(reviewers)

    proposals_info = {prop: get_submission_info(prop) for prop in proposal_list}
    reviewers_info = {rev: get_reviewer_info(rev) for rev in reviewer_list}
    num_workers = len(reviewers_info)
    num_tasks = len(proposals_info)

    costs = [
        [reward_cost(prop_info, rev_info) for prop, prop_info in proposals_info.items()]
        for rev, rev_info in reviewers_info.items()
    ]
    invalid = [
        [
            is_incompatible(prop_info, rev_info, committee)
            for prop, prop_info in proposals_info.items()
        ]
        for rev, rev_info in reviewers_info.items()
    ]

    solver = pywraplp.Solver.CreateSolver(method)

    if not solver:
        return

    # x[i, j] is an array of 0-1 variables, which will be 1
    # if worker i is assigned to task j.
    x = {
        (i, j): solver.IntVar(0, 1, f"")
        for i in range(num_workers) for j in range(num_tasks)
    }

    # Each worker is assigned to at most max_workload tasks.
    for i in range(num_workers):
        solver.Add(solver.Sum([x[i, j] for j in range(num_tasks)]) <= max_workload)

    # Each task is assigned to min_assignment workers.
    max_assignment = min_assignment if committee else min_assignment + 2
    for j in range(num_tasks):
        solver.Add(solver.Sum([x[i, j] for i in range(num_workers)]) >= min_assignment)
        solver.Add(solver.Sum([x[i, j] for i in range(num_workers)]) <= max_assignment)

        # no task is assigned to incompatible workers
        solver.Add(
            solver.Sum([x[i, j] * invalid[i][j] for i in range(num_workers)]) == 0
        )

    # Objective
    objective_terms = []
    for i in range(num_workers):
        for j in range(num_tasks):
            objective_terms.append(costs[i][j] * x[i, j])

    solver.Maximize(solver.Sum(objective_terms))
    print(f"Solving with {solver.SolverVersion()}")
    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        print(f"Total cost = {solver.Objective().Value()}\n")
        assignments = {
            proposal_list[j]: {
                reviewer_list[i]
                for i in range(num_workers)
                if (x[i, j].solution_value() > 0.5)
            }
            for j in range(num_tasks)
        }
    else:
        print("No solution found.")
        assignments = {}
    return assignments, solver, status


def assign_mip(cycle, track, method: str = Literal['SCIP', 'CLP', 'GLOP']) -> tuple[dict, bool]:
    """
    Assign reviewers to proposals using linear/constrained optimization
    :param cycle: Review Cycle
    :param track: Review Track
    :param method: one of 'SCIP', 'CLP', 'GLOP'
    :return: assignments dictionary mapping submission to a set of reviewers, boolean indicating success of assignment
    """

    reviewers = cycle.reviewers.filter(committee__isnull=True).exclude(techniques__isnull=True).distinct()
    committee = track.committee.all()
    submissions = cycle.submissions.filter(track=track).order_by('pk').distinct()
    results = {}
    max_proposals = track.max_proposals
    paginator = Paginator(submissions, 100)
    success = []
    for page in paginator.page_range:
        proposals = paginator.page(page).object_list
        prop_results, solver, status = mip_optimize(proposals, reviewers, track.min_reviewers, max_proposals)
        print(f'External Reviewers:  Page {page} of {paginator.num_pages}')
        print(f"Objective : {solver.Objective().Value()}")
        print(f"Duration  : {solver.WallTime():0.2f} ms")
        print(f"Status    : {status}")
        success.append(status in {solver.OPTIMAL, solver.FEASIBLE})

        com_max = 2 + proposals.count() // max(1, committee.count())
        com_results, solver, status = mip_optimize(proposals, committee, 1, com_max, committee=True)
        print(f'Committee Members:  Page {page} of {paginator.num_pages}')
        print(f"Objective : {solver.Objective().Value()}")
        print(f"Duration  : {solver.WallTime():0.2f} ms")
        print(f"Status    : {status}")
        success.append(status in {solver.OPTIMAL, solver.FEASIBLE})

        for prop, revs in com_results.items():
            prop_results[prop] |= set(revs)

        results.update(prop_results)

    return results, any(success)


def optimize_brute_force(submissions, reviewers, cycle, min_assignment=1, max_workload=4, committee=False):
    """
    Given a set of submissions and reviewers, assign reviewers
    :param submissions: submissions queryset
    :param reviewers: reviewers queryset
    :param cycle: review cycle
    :param min_assignment: minimum number of reviews to assign
    :param max_workload: maximum workload for each reviewer
    :param committee: whether this is a committee assignment or now
    :return: assignments dictionary mapping submission to a set of reviewers
    """
    proposals_info = {prop.pk: get_submission_info(prop) for prop in submissions}
    reviewers_info = {rev.pk: get_reviewer_info(rev) for rev in reviewers}

    assignments = defaultdict(set)
    for submission in submissions.order_by('?'):
        prop = proposals_info[submission.pk]
        tech_filter = Q(techniques__in=prop['techniques'])
        area_filter = Q(areas__in=prop['areas'])

        filters = tech_filter & area_filter
        matched_reviewers = reviewers.filter(filters).annotate(
            num_reviews=Sum(
                Case(
                    When(Q(user__reviews__cycle=cycle), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ),
        ).filter(num_reviews__lt=max_workload).order_by().distinct()

        conflicts = [
            rev.pk for rev in matched_reviewers
            if veto_conflict(prop, reviewers_info[rev.pk])
        ]

        valid_reviewers = matched_reviewers.exclude(pk__in=conflicts).order_by('?')
        print(submission.pk, valid_reviewers.count(), len(conflicts))

        if valid_reviewers.count() > min_assignment:
            assignments[submission] |= set(valid_reviewers[:min_assignment])
        else:
            assignments[submission] |= set(valid_reviewers.all())

    return assignments


def assign_brute_force(cycle, track) -> tuple[dict, bool]:
    """
    Assign reviewers to proposals using brute force
    :param cycle: Review Cycle
    :param track: Review Track
    :return: assignments dictionary mapping submission to a set of reviewers, boolean indicating success of assignment
    """

    submissions = cycle.submissions.exclude(techniques__isnull=True).filter(track=track).distinct()
    reviewers = cycle.reviewers.filter(committee__isnull=True).exclude(techniques__isnull=True).order_by('?').distinct()
    assignments = optimize_brute_force(submissions, reviewers, cycle, track.min_reviewers, track.max_proposals)

    committee = track.committee.order_by('?')
    if committee.count():
        committee_assignments = optimize_brute_force(submissions, committee, cycle, 1, 2 + submissions.count() // committee.count())
        for submission, reviewers in committee_assignments.items():
            assignments[submission] |= set(reviewers)

    num_assigned = sum(len(revs) for revs in assignments.values())

    return assignments, num_assigned > 0


def assign_reviewers(cycle, track) -> tuple[dict, bool]:
    """
    Perform assignments according to settings options
    :param cycle: Review Cycle
    :param track: Review Track
    :return:
    """
    if USO_REVIEW_ASSIGNMENT == "CMACRA":
        return assign_mip(cycle, track, 'CLP')
    elif USO_REVIEW_ASSIGNMENT == "MIP":
        return assign_mip(cycle, track, 'SCIP')
    else:
        return assign_brute_force(cycle, track)


DECISIONS = Choices(
    (0, 'exempt', 'Exempt'),
    (1, 'protocol', 'Protocol'),
    (2, 'ethics', 'Ethics'),
    (3, 'rejected', 'Rejected'),
)


def color_scale(val, lo=1, hi=5, max_saturation=180):
    if not isinstance(val, float):
        return ''
    n = int(min(255, max(0, (val - lo) * max_saturation // (hi - lo))))
    return '#%02x%02x%02x' % (n, max_saturation - n, 0)


def score_format(val, obj=None):
    if val:
        return mark_safe(f"<span style='font-weight: bold; color: {color_scale(val, 1, 5)};'>{val:.2f}</span>")
    else:
        return mark_safe("&hellip;")


def stdev_format(val, obj=None):
    if val:
        return mark_safe(f"<span style='font-weight: bold; color: {color_scale(val, 0.1, 3)};'>{val:.2f}</span>")
    else:
        return mark_safe("&hellip;")


def get_techniques_matrix(cycle=None, sel_techs=(), sel_fac=None):
    """Generate a dictionary mapping each technique to a list of available facilities and
    each facility to a list available techniques. Entries in the lists are tuples of the form
    (primary_key, Unicode label, bool selected). The selected field will be true if the primary key was passed in
    the sel_techs or sel_fac.
    """
    from proposals import models
    tech_facs = defaultdict(list)
    fac_techs = defaultdict(list)

    if not cycle:
        return {'techniques': [], 'facilities': []}

    if not sel_techs:
        sel_techs = [0]

    for conf in models.FacilityConfig.objects.active(d=cycle.start_date).accepting():
        for t in conf.items.values_list('technique', flat=True):
            tech_facs[t].append(conf.facility.pk)
            fac_techs[conf.facility.pk].append(t)

    techs = models.Technique.objects.filter(pk__in=list(tech_facs.keys())).annotate(
        selected=Case(
            When(pk__in=sel_techs, then=Value(1)),
            default=Value(0), output_field=BooleanField()
        )
    ).order_by('name')

    facilities = models.Facility.objects.filter(pk__in=list(fac_techs.keys())).annotate(
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
            for f in facilities
        ]
    }
    return matrix
