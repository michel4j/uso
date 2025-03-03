from collections import defaultdict
from datetime import timedelta

from django.db.models import Min, F
from django.utils import timezone

from isocron import BaseCronJob
from notifier import notify
from . import utils


class CreateCycles(BaseCronJob):
    run_every = "P2D"

    def do(self):
        from proposals import models
        dt = timezone.now().date()
        out = ""

        # if there are no cycles, create the first two.
        if not models.ReviewCycle.objects.filter().count():
            out = utils.create_cycle(dt)

        # We should always have 4 future cycles, 1 year in advance for schedule
        if models.ReviewCycle.objects.filter(start_date__gt=dt).count() < 4:
            last_cycle = models.ReviewCycle.objects.latest('start_date')
            out = utils.create_cycle(last_cycle.start_date)

        return out


class CycleStateManager(BaseCronJob):
    run_every = "PT2H"

    def do(self):
        from . import models
        today = timezone.localtime(timezone.now()).date()
        yesterday = today - timedelta(days=1)

        # check and switch to open
        models.ReviewCycle.objects.filter(
            open_date__lte=today, close_date__gte=today, state=models.ReviewCycle.STATES.pending
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
    run_every = "P1D"
    run_at = ['02:00']

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
                return "{} reviewer reminders sent".format(len(list(info.values())))


class CloseReviews(BaseCronJob):
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

        # Close RA reviews if they are complete
        cycle = models.ReviewCycle.objects.filter(open_date__lt=today, end_date__gt=today).first()
        for track in cycle.tracks().filter(require_call=False):
            revs = models.Review.objects.filter(cycle=cycle, stage__track=track, state=models.Review.STATES.submitted)
            if revs.exists():
                revs.update(state=models.Review.STATES.closed, modified=timezone.now())
                logs.append(f"{revs.count()} {track} Reviews closed")

        ra_subs = cycle.submissions.filter(track__require_call=False).exclude(state=models.Submission.STATES.complete)
        to_close = ra_subs.annotate(min_state=Min('reviews__state')).values('id', 'min_state').filter(min_state=models.Review.STATES.closed)
        if to_close:
            for submission in cycle.submissions.filter(pk__in=[s['id'] for s in to_close]):
                submission.close()
            logs.append(f"{len(to_close)} RA Reviews closed")

        return '\n'.join(logs)
