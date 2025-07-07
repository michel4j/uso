from collections import defaultdict
from datetime import timedelta

from django.db.models import Min, F, Max
from django.utils import timezone

from isocron import BaseCronJob
from misc.utils import debug_value
from notifier import notify
from . import utils


class CreateCycles(BaseCronJob):
    """
    Create next cycles if they do not exist.
    Ensure there are always 4 future cycles, two years in advance for scheduling.
    """
    run_every = "P2D"

    def do(self):
        from proposals import models
        today = timezone.now().date()
        out = ""

        # if there are no cycles, create the first four.
        if not models.ReviewCycle.objects.filter().count():

            six_months = timedelta(days=6*4*7)
            dt = today - six_months
            for i in range(4):
                out = utils.create_cycle(dt)
                dt = dt + six_months

        # We should always have 4 future cycles, 1 year in advance for schedule
        if models.ReviewCycle.objects.filter(start_date__gt=today).count() < 4:
            last_cycle = models.ReviewCycle.objects.latest('start_date')
            out = utils.create_cycle(last_cycle.start_date)

        return out


class CycleStateManager(BaseCronJob):
    """
    Manage the state of review cycles based on their dates.
    """
    run_every = "PT2H"

    def do(self):
        from . import models
        today = timezone.localtime(timezone.now()).date()

        # check and switch to open
        models.ReviewCycle.objects.filter(
            open_date__lte=today, state=models.ReviewCycle.STATES.pending
        ).update(state=models.ReviewCycle.STATES.open)

        # check and switch to assign
        models.ReviewCycle.objects.filter(
            close_date__lte=today, state=models.ReviewCycle.STATES.open,
        ).update(
            state=models.ReviewCycle.STATES.assign
        )

        # check and switch to active
        models.ReviewCycle.objects.exclude(state=models.ReviewCycle.STATES.active).filter(
            start_date__lte=today, end_date__gte=today
        ).update(state=models.ReviewCycle.STATES.active)

        # check and switch to archive
        models.ReviewCycle.objects.exclude(
            state=models.ReviewCycle.STATES.archive
        ).filter(end_date__lt=today).update(
            state=models.ReviewCycle.STATES.archive
        )


class NotifyReviewers(BaseCronJob):
    """
    Notify reviewers about pending reviews.
    """
    run_every = "P1D"

    def do(self):
        from . import models
        cycle = models.ReviewCycle.objects.next()
        today = timezone.localtime(timezone.now())
        yesterday = today - timedelta(days=1)
        if cycle:
            # Notify technical reviews one day later to avoid spamming
            reviews = models.Review.objects.technical().filter(
                state=models.Review.STATES.pending, created__lte=yesterday
            )
            count = utils.notify_reviewers(reviews)
            reviews.update(state=models.Review.STATES.open)
            if count:
                return f"{count} reviewer notification(s) sent"


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


class SubmissionStateManager(BaseCronJob):
    """
    Manage Submission State based on completion of reviews.
    """
    run_every = "PT15M"

    def do(self):
        from proposals import models

        logs = []
        now = timezone.localtime(timezone.now())

        # at least one review submitted, switch pending to in progress
        subs = models.Submission.objects.annotate(max_state=Max('reviews__state'), min_state=Min('reviews__state'))
        started_subs = subs.filter(
            max_state__in=[1, 2], state=models.Submission.STATES.pending
        )
        if started_subs.exists():
            started_subs.update(state=models.Submission.STATES.started, modified=now)
            logs.append(f"{started_subs.count()} Submissions started review")

        completed_subs = subs.filter(
            min_state=models.Review.STATES.submitted, state__lt=models.Submission.STATES.reviewed
        )
        if completed_subs.exists():
            for sub in completed_subs:
                sub.close()
            logs.append(f"{completed_subs.count()} Submissions completed review")

        return '\n'.join(logs)


class CloseReviews(BaseCronJob):
    """
    Close reviews that are past their due date.
    """
    run_every = "PT15M"

    def do(self):
        from proposals import models
        cycle = models.ReviewCycle.objects.review().first()
        logs = []
        today = timezone.localtime(timezone.now()).date()
        if cycle and cycle.due_date < today:
            # Do not process Rapid Access Track
            for track in cycle.tracks().filter(require_call=True):
                revs = models.Review.objects.filter(
                    cycle=cycle, stage__track=track,
                    state=models.Review.STATES.submitted
                )
                if revs.exists():
                    revs.update(state=models.Review.STATES.closed, modified=timezone.now())
                    logs.append(f"{revs.count()} {track} Reviews closed")

                for submission in cycle.submissions.filter(track=track):
                    submission.close()

        # Close Non-call reviews if they are complete
        cycle = models.ReviewCycle.objects.filter(open_date__lt=today, end_date__gt=today).first()
        for track in cycle.tracks().filter(require_call=False):
            revs = models.Review.objects.filter(cycle=cycle, stage__track=track, state=models.Review.STATES.submitted)
            if revs.exists():
                revs.update(state=models.Review.STATES.closed, modified=timezone.now())
                logs.append(f"{revs.count()} {track} Reviews closed")

        return '\n'.join(logs)
