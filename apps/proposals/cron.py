from collections import defaultdict
from datetime import timedelta

from django.db.models import Q, QuerySet, Max
from django.utils import timezone

from isocron import BaseCronJob
from notifier import notify
from . import utils

FUTURE_CYCLES = 2


class CreateCycles(BaseCronJob):
    """
    Create next cycles if they do not exist.
    Ensure there are always cycles two years in advance for scheduling.
    """
    run_every = "P2D"
    pending_types: QuerySet = None

    def is_ready(self):
        from proposals import models
        today = timezone.now().date()
        in_future_years = today.year + FUTURE_CYCLES

        # Check if there are cycles for the next two years
        # the end_date of the latest cycle from each type should be at least 2 years from today
        self.pending_types = models.CycleType.objects.filter(active=True).annotate(
            max_year=Max('cycles__end_date__year')
        ).filter(Q(max_year__isnull=True) | Q(max_year__lt=in_future_years))

        return self.pending_types.exists()

    def do(self):
        logs = []
        today = timezone.now().date()
        in_future_years = today.year + FUTURE_CYCLES
        min_year = min(self.pending_types.values_list('max_year', flat=True))
        for year in range(min_year + 1, in_future_years + 1):
            for pending_type in self.pending_types.order_by('start_date__month'):
                max_year = pending_type.max_year or today.year - 1
                if max_year < year:
                    created = pending_type.create_next(year=year)
                    logs.append(f"Created cycle for {pending_type.name} for year {year}")
        return '\n'.join(logs)


class CycleStateManager(BaseCronJob):
    """
    Manage the state of review cycles based on their dates.
    """
    run_every = "PT2H"

    def do(self):
        from . import models
        today = timezone.localtime(timezone.now()).date()
        logs = []
        # check and switch to open
        opened = models.ReviewCycle.objects.filter(
            open_date__lte=today, state=models.ReviewCycle.STATES.pending
        ).update(state=models.ReviewCycle.STATES.open)
        if opened:
            logs.append(f"{opened} review cycle(s) opened")

        # check and switch to assign
        assigned = models.ReviewCycle.objects.filter(
            close_date__lte=today, state=models.ReviewCycle.STATES.open,
        ).update(
            state=models.ReviewCycle.STATES.assign
        )
        if assigned:
            logs.append(f"{assigned} review cycle(s) switched to assign state")

        # check and switch to review based on dates and if submissions are started
        reviewing = models.ReviewCycle.objects.exclude(state=models.ReviewCycle.STATES.review).filter(
            start_date__lte=today, end_date__gte=today, state=models.ReviewCycle.STATES.assign,
            submissions__state__gte=models.Submission.STATES.started
        ).update(state=models.ReviewCycle.STATES.review)
        if reviewing:
            logs.append(f"{reviewing} review cycle(s) switched to review state")

        # check and switch to evaluation
        evaluating = models.ReviewCycle.objects.exclude(state=models.ReviewCycle.STATES.evaluation).filter(
            due_date__lte=today, alloc_date__gte=today,
        ).update(state=models.ReviewCycle.STATES.evaluation)
        if evaluating:
            logs.append(f"{evaluating} review cycle(s) switched to evaluation state")

        # check and switch to scheduling
        scheduling = models.ReviewCycle.objects.exclude(state=models.ReviewCycle.STATES.schedule).filter(
            alloc_date__lte=today, start_date__gt=today,
        ).update(state=models.ReviewCycle.STATES.schedule)
        if scheduling:
            logs.append(f"{scheduling} review cycle(s) switched to scheduling state")

        # check and switch to active
        active = models.ReviewCycle.objects.exclude(state=models.ReviewCycle.STATES.active).filter(
            start_date__lte=today, end_date__gte=today
        ).update(state=models.ReviewCycle.STATES.active)
        if active:
            logs.append(f"{active} review cycle(s) switched to active state")

        # check and switch to archive
        archived = models.ReviewCycle.objects.exclude(
            state=models.ReviewCycle.STATES.archive
        ).filter(end_date__lt=today).update(
            state=models.ReviewCycle.STATES.archive
        )
        if archived:
            logs.append(f"{archived} review cycle(s) archived")

        return '\n'.join(logs)


class StartReviews(BaseCronJob):
    """
    Open pending reviews and notify reviewers, once daily. Only reviews from auto-start stages
    are processed. Non auto-start reviews can be opened through the cycle management interface.
    """
    run_every = "P1D"

    def do(self):
        from . import models
        logs = []

        # reviews one day later to avoid spamming
        reviews = models.Review.objects.filter(
            state=models.Review.STATES.pending, stage__auto_start=True, due_date__isnull=False
        )
        count = utils.notify_reviewers(reviews)
        reviews.update(state=models.Review.STATES.open)

        if count:
            logs.append(f"{count} reviewer notification(s) sent")

        submissions = models.Submission.objects.filter(
            state=models.Submission.STATES.pending, reviews__state=models.Review.STATES.open
        )
        if submissions.count():
            submissions.update(state=models.Submission.STATES.started)
            logs.append(f"{submissions.count()} submission(s) started review process")

        return '\n'.join(logs)


class RemindReviewers(BaseCronJob):
    """
    Remind reviewers about reviews that are due tomorrow.
    """
    run_every = "T02:00"    # every day at 2 AM local time

    def do(self):
        from proposals import models
        today = timezone.localtime(timezone.now()).date()
        tomorrow = today + timedelta(days=1)
        reviews = models.Review.objects.filter(due_date=tomorrow, state=models.Review.STATES.open)
        if reviews:
            info = defaultdict(list)

            # gather all reviews for each reviewer
            for rev in reviews.all():
                if rev.reviewer:
                    info[rev.reviewer].append(rev)
                else:
                    info[rev.role].append(rev)

            # generate notifications
            for recipient, revs in list(info.items()):
                notify.send([recipient], 'review-reminder', level=notify.LEVELS.important, context={
                    'reviews': revs,
                    'due_date': tomorrow,
                })

            if len(list(info.values())):
                return f"{len(list(info.values()))} reviewer reminders sent"
        return ''


class AdvanceReviewWorkflow(BaseCronJob):
    """
    Manage Submission State based on completion of reviews, creates reviews for next stages.
    """
    run_every = "PT30M"
    submissions: QuerySet

    def is_ready(self):
        from proposals import models
        now = timezone.localtime(timezone.now())
        self.submissions = models.Submission.objects.filter(
            Q(cycle__due_date__lt=now, cycle__end_date__gt=now, track__require_call=True) |
            Q(cycle__start_date__lte=now, cycle__end_date__gt=now, track__require_call=False),
            state__lt=models.Submission.STATES.reviewed,
        )
        return self.submissions.exists()

    def do(self):
        logs = []
        for submission in self.submissions:
            sub_logs = utils.advance_review_workflow(submission)
            logs.extend(sub_logs)

        return '\n'.join(logs)

