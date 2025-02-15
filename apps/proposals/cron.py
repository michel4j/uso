from collections import defaultdict
from datetime import timedelta

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
        from proposals import models
        today = timezone.localtime(timezone.now()).date()
        yesterday = today - timedelta(days=1)

        models.ReviewCycle.objects.filter(
            open_date__lte=today, close_date__gte=today, state=models.ReviewCycle.STATES.pending
        ).update(state=models.ReviewCycle.STATES.open)

        models.ReviewCycle.objects.filter(close_date=yesterday, state=models.ReviewCycle.STATES.open).update(
            state=models.ReviewCycle.STATES.assign
        )

        cur_cycles = models.ReviewCycle.objects.exclude(state=models.ReviewCycle.STATES.active).filter(
            start_date__lte=today, end_date__gte=today
        )
        if cur_cycles.exists():
            cur_cycles.update(state=models.ReviewCycle.STATES.active)
            cycle = cur_cycles.last()
            next_cycle = models.ReviewCycle.objects.next(cycle.start_date)
            next_cycle.reviewers.add(*cycle.reviewers.all())

        models.ReviewCycle.objects.exclude(state=models.ReviewCycle.STATES.archive).filter(end_date__lt=today).update(
            state=models.ReviewCycle.STATES.archive)


class NotifyReviewers(BaseCronJob):
    run_every = "P1D"

    def do(self):
        from proposals import models
        cycle = models.ReviewCycle.objects.next()
        today = timezone.localtime(timezone.now()).date()
        yesterday = today - timedelta(days=1)
        if cycle:
            info = defaultdict(list)
            reviews = models.Review.objects.none()

            # Notify technical reviews one day later
            reviews |= models.Review.objects.technical().filter(
                state=models.Review.STATES.pending, created__lte=yesterday
            )

            # gather all reviews for each reviewer
            for rev in reviews.all():
                if rev.reviewer:
                    info[rev.reviewer].append(rev)
                else:
                    info[rev.role].append(rev)

            # generate notifications
            for recipient, revs in list(info.items()):
                notify.send([recipient], 'review-request', level=notify.LEVELS.important, context={
                    'reviews': revs,
                })
                models.Review.objects.filter(pk__in=[r.pk for r in revs]).update(state=models.Review.STATES.open)

            if len(list(info.values())):
                return "{} reviewer notifications sent".format(len(list(info.values())))


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
    run_every = "PT4H"

    def do(self):
        from proposals import models
        cycle = models.ReviewCycle.objects.review().first()
        logs = []
        today = timezone.localtime(timezone.now()).date()
        if cycle and cycle.due_date < today:
            # Do not process Rapid Access Track
            for track in cycle.tracks().exclude(special=True):
                revs = models.Submission.objects.filter(track=track, cycle=cycle).values_list('reviews', flat=True)
                queryset = models.Review.objects.filter(
                    state__in=[models.Review.STATES.open, models.Review.STATES.submitted],
                    pk__in=revs,
                    cycle=cycle
                )
                queryset.update(state=models.Review.STATES.closed)
                for submission in cycle.submissions.filter(track=track):
                    submission.close()
                if queryset.count():
                    logs.append(f"{queryset.count()} {track.acronym} Reviews closed")

        ra_reviews = models.Submission.objects.filter(track__special=True).values_list('reviews', flat=True)

        # for Rapid Access Track change review state to complete if review has been completed more than 1 hour ago.
        queryset = models.Review.objects.filter(
            pk__in=ra_reviews, state__lt=models.Review.STATES.closed, is_complete=True,
            # modified__date__lte=timezone.localtime(timezone.now() - timedelta(days=1)).date()
        )

        queryset.update(state=models.Review.STATES.closed, modified=timezone.now())
        ra_submissions = models.Submission.objects.filter(
            track__special=True,
            state__lt=models.Submission.STATES.reviewed).exclude(
            reviews__state__lt=models.Review.STATES.closed
        )
        for submission in ra_submissions:
            submission.close()

        if queryset.count():
            logs.append("{} RA Reviews closed".format(queryset.count()))

        return '\n'.join(logs)
