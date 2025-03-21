
from collections import defaultdict
from datetime import date, timedelta, datetime
from typing import Literal

from django.conf import settings
from django.db.models import Case, When, BooleanField, Value, Q, Sum, IntegerField, F
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models.functions import Concat, Lower
from django.utils.safestring import mark_safe
from docutils.nodes import entry
from model_utils import Choices

from notifier import notify

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
        'areas': set(reviewer.areas.values_list('pk', flat=True)),
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
        veto_technique(proposal, reviewer),
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
    # reward for matching technique
    return 100 * len(proposal['techniques'] & reviewer['techniques']) * len(proposal['areas'] & reviewer['areas'])


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


class Assigner:
    def __init__(self, submissions, reviewers, stage, cycle):
        self.cycle = cycle
        self.track = stage.track
        self.submissions = submissions
        self.reviewers = reviewers

        self.committee = reviewers.filter(committee=self.track)
        self.pool = reviewers.filter(committee__isnull=True).order_by('?')[:200]

        self.prop_info = {
            item['pk']: item
            for item in self.submissions.values('pk').annotate(
                areas=ArrayAgg('proposal__areas__pk', distinct=True),
                techs=ArrayAgg('techniques__technique__pk', distinct=True),
                emails=F('proposal__team'),
                names=F('proposal__details__inappropriate_reviewers')
            )
        }
        for pk, item in self.prop_info.items():
            names = set() if not item['names'] else {
                f"{r['last_name']},{r['first_name']}".strip().lower() for r in item.pop('names')
            }
            self.prop_info[item['pk']].update({
                'techs': set(item['techs']),
                'areas': set(item['areas']),
                'names': names,
                'emails': set(item['emails']),
            })
        self.rev_info = {
            item['pk']: item
            for item in self.reviewers.values('pk').annotate(
                areas=ArrayAgg('areas__pk', distinct=True),
                techs=ArrayAgg('techniques__pk', distinct=True),
                name=Lower(Concat('user__last_name', Value(','), 'user__first_name')),
                email=Lower('user__email'),
                alt_email=Lower('user__alt_email')
            )
        }

        for pk, item in self.rev_info.items():
            self.rev_info[item['pk']].update({
                'techs': set(item['techs']),
                'areas': set(item['areas']),
                'names': {item.pop('name')},
                'emails': {item.pop('email'), item.pop('alt_email')} - {None, ''}
            })

    def get_proposal_info(self, submission):
        return self.prop_info[submission.pk]

    def get_reviewer_info(self, reviewer):
        return self.rev_info[reviewer.pk]

    def is_incompatible(self, proposal, reviewer, committee=False) -> Literal[0, 1]:
        """
        Check if a reviewer is incompatible with a submission
        :param proposal: proposal information dictionary
        :param reviewer: reviewer information dictionary
        :param committee: flag to indicate committee review
        :return: 0 if compatible, 1 if incompatible
        """
        return max(
            self.veto_conflict(proposal, reviewer),
            self.veto_technique(proposal, reviewer),
            self.veto_subject(proposal, reviewer)
        )

    def has_conflict(self, proposal, reviewer) -> Literal[0, 1]:
        """
        Check if a reviewer has a conflict with a submission
        :param proposal: proposal information dictionary
        :param reviewer: reviewer information dictionary
        """
        return self.veto_conflict(proposal.pk, reviewer.pk)

    def veto_conflict(self, proposal: int, reviewer: int, lax: bool = False) -> Literal[0, 1]:
        """
        Check if a reviewer is incompatible with a submission based on emails and names
        :param proposal: proposal pk
        :param reviewer: reviewer pk
        :param lax: ignore this check
        :return: 0 or 1
        """
        p_info = self.prop_info[proposal]
        r_info = self.rev_info[reviewer]
        if lax:
            return 0
        return 1 if any((
            p_info['emails'] & r_info['emails'],
            p_info['names'] & r_info['names'],
        )) else 0

    def veto_technique(self, proposal: int, reviewer: int, lax: bool = False) -> Literal[0, 1]:
        """
        Check if a reviewer is incompatible with a submission based on techniques
        :param proposal: proposal information
        :param reviewer: reviewer information
        :param lax: ignore this check
        :return: 0 or 1
        """
        p_info = self.prop_info[proposal]
        r_info = self.rev_info[reviewer]

        if lax:
            return 0
        return 0 if len(p_info['techs'] & r_info['techs']) else 1

    def veto_subject(self, proposal: int, reviewer: int, lax: bool = False) -> Literal[0, 1]:
        """
        Check if a reviewer is incompatible with a submission based on subject areas
        :param proposal: proposal information
        :param reviewer: reviewer information
        :param lax: ignore this check
        :return: 0 or 1
        """
        p_info = self.prop_info[proposal]
        r_info = self.rev_info[reviewer]

        if lax:
            return 0
        return 0 if len(p_info['areas'] & r_info['areas']) else 1

    def reward_cost(self, proposal, reviewer) -> float:
        """
        Calculate the reward cost for a proposal-reviewer pair
        :param proposal: proposal
        :param reviewer: reviewer
        :return: reward
        """
        # reward for matching technique
        p_info = self.prop_info[proposal]
        r_info = self.rev_info[reviewer]
        return 100 * len(p_info['techs'] & r_info['techs']) * len(p_info['areas'] & r_info['areas'])

    def penalty_cost(self, proposal, reviewer):
        """
        Calculate the penalty cost for a proposal-reviewer pair
        :param proposal: proposal
        :param reviewer: reviewer
        :return: penalty
        """
        p_info = self.prop_info[proposal]
        r_info = self.rev_info[reviewer]
        cost = 100
        # reward for matching technique
        scale = len(p_info['techs'] & r_info['techs'])
        scale *= len(p_info['areas'] & r_info['areas'])
        cost = max(0, cost - scale * 10)
        return cost


def mip_optimize(assigner, min_assignment=1, max_workload=4, committee=False, method='SCIP'):
    """
    Given a set of submissions and reviewers, assign reviewers
    :param assigner: Assigner instance
    :param min_assignment: minimum number of reviews to assign
    :param max_workload: maximum workload for each reviewer
    :param committee: whether this is a committee assignment or now
    :param method: solver method, one of 'SCIP', 'CLP', 'GLOP'
    :param assigner: Assigner instance
    :return: assignments dictionary mapping submission to a set of reviewers
    """

    import numpy
    from ortools.linear_solver import pywraplp

    proposal_list = list(assigner.submissions)
    if committee:
        reviewer_list = list(assigner.committee)
    else:
        reviewer_list = list(assigner.pool)

    print('Mixed Integer Programming Optimization')
    invalid = numpy.array([
        [
            assigner.is_incompatible(prop.pk, rev.pk, committee)
            for prop in proposal_list
        ]
        for rev in reviewer_list
    ])
    print('Done calculating costs! Will now optimize...')

    num_workers = len(reviewer_list)
    num_tasks = len(proposal_list)
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

        # no reviewer is assigned to incompatible proposal
        solver.Add(
            solver.Sum([x[i, j] * invalid[i][j] for j in range(num_tasks)]) == 0
        )

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
    costs = [
        [assigner.reward_cost(prop.pk, rev.pk) for prop in proposal_list]
        for rev in reviewer_list
    ]
    for i in range(num_workers):
        for j in range(num_tasks):
            solver.Add(x[i, j] * invalid[i][j] == 0)
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


def assign_mip(cycle, stage, method: str = Literal['SCIP', 'CLP', 'GLOP']) -> tuple[dict, bool]:
    """
    Assign reviewers to proposals using linear/constrained optimization
    :param cycle: Review Cycle
    :param stage: Review Stage
    :param method: one of 'SCIP', 'CLP', 'GLOP'
    :return: assignments dictionary mapping submission to a set of reviewers, boolean indicating success of assignment
    """
    from .models import Reviewer
    track = stage.track
    reviewers = Reviewer.objects.available(cycle).order_by('?').distinct()
    proposals = cycle.submissions.filter(track=track).order_by('?').distinct()
    results = {}
    max_workload = track.max_workload

    print(f"Assigning {proposals.count()} proposals to {reviewers.count()} reviewers.")

    assigner = Assigner(proposals, reviewers, stage, cycle)

    success = []
    prop_results, solver, status = mip_optimize(assigner, stage.min_reviews, max_workload, method=method)
    print('External Reviewers:')
    print(f"Objective : {solver.Objective().Value()}")
    print(f"Duration  : {solver.WallTime():0.2f} ms")
    print(f"Status    : {status}")
    success.append(status in {solver.OPTIMAL, solver.FEASIBLE})
    
    committee = assigner.committee
    com_max = 2 + proposals.count() // max(1, committee.count())
    com_results, solver, status = mip_optimize(assigner, track.min_reviewers, com_max, committee=True, method=method)
    print('Committee Members:')
    print(f"Objective : {solver.Objective().Value()}")
    print(f"Duration  : {solver.WallTime():0.2f} ms")
    print(f"Status    : {status}")
    success.append(status in {solver.OPTIMAL, solver.FEASIBLE})

    for prop, revs in com_results.items():
        prop_results[prop] |= set(revs)

    results.update(prop_results)

    return results, any(success)


def optimize_brute_force(assigner, min_assignment=1, max_workload=4, committee=False):
    """
    Given a set of submissions and reviewers, assign reviewers
    :param assigner: assigner instance
    :param min_assignment: minimum number of reviews to assign
    :param max_workload: maximum workload for each reviewer
    :param committee: whether this is a committee assignment or now
    :return: assignments dictionary mapping submission to a set of reviewers
    """

    cycle = assigner.cycle
    reviewers = assigner.committee if committee else assigner.pool
    submissions = assigner.submissions

    assignments = defaultdict(set)
    for submission in submissions.order_by('?'):
        prop = assigner.get_proposal_info(submission)
        tech_filter = Q(techniques__in=prop['techs'])
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
            if assigner.veto_conflict(prop, assigner.veto_conflict(submission.pk, rev.pk))
        ]

        valid_reviewers = matched_reviewers.exclude(pk__in=conflicts).order_by('?')
        if valid_reviewers.count() > min_assignment:
            assignments[submission] |= set(valid_reviewers[:min_assignment])
        else:
            assignments[submission] |= set(valid_reviewers.all())

    return assignments


def assign_brute_force(cycle, stage) -> tuple[dict, bool]:
    """
    Assign reviewers to proposals using brute force
    :param cycle: Review Cycle
    :param stage: Review stage
    :return: assignments dictionary mapping submission to a set of reviewers, boolean indicating success of assignment
    """
    from .models import Reviewer
    track = stage.track
    reviewers = Reviewer.objects.available(cycle).order_by('?').distinct()
    proposals = cycle.submissions.filter(track=track).order_by('?').distinct()
    max_workload = track.max_workload

    print(f"Assigning {proposals.count()} proposals to {reviewers.count()} reviewers.")
    assigner = Assigner(proposals, reviewers, stage, cycle)
    assignments = optimize_brute_force(assigner, stage.min_reviews, max_workload)

    committee = track.committee.order_by('?')
    if committee.count():
        committee_assignments = optimize_brute_force(
            assigner, 1, 2 + proposals.count() // committee.count()
        )
        for submission, reviewers in committee_assignments.items():
            assignments[submission] |= set(reviewers)

    num_assigned = sum(len(revs) for revs in assignments.values())
    return assignments, num_assigned > 0


def assign_reviewers(cycle, stage) -> tuple[dict, bool]:
    """
    Perform assignments according to settings options
    :param cycle: Review Cycle
    :param stage: Review Stage
    :return:
    """
    if USO_REVIEW_ASSIGNMENT == "CMACRA":
        return assign_mip(cycle, stage, method='CLP')
    elif USO_REVIEW_ASSIGNMENT == "MIP":
        return assign_mip(cycle, stage, method='SCIP')
    else:
        return assign_brute_force(cycle, stage)


DECISIONS = Choices(
    (0, 'exempt', 'Exempt'),
    (1, 'protocol', 'Protocol'),
    (2, 'ethics', 'Ethics'),
    (3, 'rejected', 'Rejected'),
)


def scale_color(val, lo=1, hi=5, max_saturation=180):
    if not isinstance(val, float):
        return ''
    n = int(min(255, max(0, (val - lo) * max_saturation // (hi - lo))))
    return '#%02x%02x%02x' % (n, max_saturation - n, 0)


def score_format(val, obj=None):
    if val:
        return mark_safe(f"<span style='font-weight: bold; color: {scale_color(val, 1, 5)};'>{val:.2f}</span>")
    else:
        return mark_safe("&hellip;")


def stdev_format(val, obj=None):
    if val:
        return mark_safe(f"<span style='font-weight: bold; color: {scale_color(val, 0.1, 3)};'>{val:.2f}</span>")
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


def notify_reviewers(reviews):
    """
    Notify reviewers of pending reviews to complete
    :param reviews: Reviews queryset
    :return: number of notifications sent
    """
    info = defaultdict(list)
    # gather all reviews for each reviewer
    for review in reviews.all():
        if review.reviewer:
            info[review.reviewer].append(review)
        else:
            info[review.role].append(review)

    # generate notifications
    count = 0
    for recipient, user_reviews in info.items():
        notify.send(
            [recipient], 'review-request', level=notify.LEVELS.important, context={
                'reviews': user_reviews,
            }
        )
        count += 1
    return count


def user_format(value, obj):
    return str(obj.proposal.spokesperson)

