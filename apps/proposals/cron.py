from collections import defaultdict
from datetime import timedelta

from django.db.models import Min, F, Max, Q
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

        today = timezone.localtime(timezone.now())
        yesterday = today - timedelta(days=1)

        # Notify technical reviews one day later to avoid spamming
        reviews = models.Review.objects.technical().filter(
            state=models.Review.STATES.pending, created__lte=yesterday
        )
        count = utils.notify_reviewers(reviews)
        reviews.update(state=models.Review.STATES.open)
        if count:
            return f"{count} reviewer notification(s) sent"
        return ''


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


class SubmissionStateManager(BaseCronJob):
    """
    Manage Submission State based on completion of reviews.
    """
    run_every = "PT15M"

    def do(self):
        from proposals import models

        logs = []
        now = timezone.localtime(timezone.now())
        tracks = models.ReviewTrack.objects.annotate(max_stage=Max('stages__position'))

        for track in tracks:
            # at least one review submitted, switch pending to in progress
            subs = models.Submission.objects.filter(
                Q(cycle__due_date__lt=now, cycle__end_date__gt=now, track__require_call=True) |
                Q(cycle__start_date__lte=now, cycle__end_date__gt=now, track__require_call=False),
                track=track,
            ).annotate(
                max_state=Max('reviews__state'),
                min_state=Min('reviews__state'),
                max_stage=Max('reviews__stage__position')
            )

            # at least one review submitted, switch pending to in progress
            started = subs.filter(
                max_state__in=[1, 2], state=models.Submission.STATES.pending
            )
            if started.exists():
                started.update(state=models.Submission.STATES.started, modified=now)
                logs.append(f"{started.count()} Submissions started review")

            # all reviews are submitted and the last stage is present
            completed = subs.filter(
                min_state=models.Review.STATES.submitted,
                max_stage=track.max_stage
            )
            if completed.exists():
                for submission in completed:
                    submission.close()
                logs.append(f"{completed.count()} {track} Submissions reviewed")

        return '\n'.join(logs)


class CloseReviews(BaseCronJob):
    """
    Close reviews that are past their due date.
    """
    run_every = "PT15M"

    def do(self):
        from proposals import models

        logs = []
        today = timezone.localtime(timezone.now()).date()
        tracks = models.ReviewTrack.objects.annotate(max_stage=Max('stages__position'))

        call_filters = {
            'cycle__due_date__lt': today,
            'cycle__start_date__gte': today,
        }
        non_call_filters = {
            'cycle__due_date__lt': today,
            'cycle__end_date__gte': today,
        }

        # Close reviews
        for track in tracks:
            revs = models.Review.objects.filter(
                Q(cycle__due_date__lt=today, cycle__end_date__gt=today, stage__track__require_call=True) |
                Q(cycle__start_date__lte=today, cycle__end_date__gt=today, stage__track__require_call=False),
                stage__track=track,
                state=models.Review.STATES.submitted,
            )

            if revs.exists():
                revs.update(state=models.Review.STATES.closed, modified=timezone.now())
                logs.append(f"{revs.count()} {track} Reviews closed")

                filters = (
                    Q(stage__blocks=False) |
                    Q(type__low_better=True, score__lt=F('stage__pass_score')) |
                    Q(type__low_better=False, score__gt=F('stage__pass_score'))
                )

                to_create = []

                for rev in revs.filter(filters, stage__position__lt=track.max_stage):
                    stage = track.stages.filter(position=rev.stage.position + 1, auto_create=True).first()
                    if not stage:
                        continue

                    due_date = min(rev.cycle.due_date, timezone.now().date() + timedelta(weeks=2))

                    technical_info = {
                        (item.config.facility.acronym.lower(), item.config.facility)
                        for item in rev.reference.techniques.all()
                    }

                    # create next stage review
                    review_type = stage.kind
                    if review_type.per_facility:
                        # create min_reviews reviews for each facility
                        to_create.extend(
                            [
                                models.Review(
                                    role=review_type.role.format(acronym),
                                    cycle=rev.cycle,
                                    reference=rev.reference,
                                    type=review_type,
                                    form_type=review_type.form_type,
                                    state=models.Review.STATES.pending,
                                    stage=stage,
                                    due_date=due_date, details={'facility': facility.pk}
                                )
                                for acronym, facility in technical_info
                                for _ in range(stage.min_reviews)
                            ]
                        )
                    else:
                        # create min_reviews reviews for proposal
                        to_create.append(
                            models.Review(
                                role=review_type.role,
                                cycle=rev.cycle,
                                stage=stage,
                                reference=rev.reference,
                                type=review_type,
                                form_type=review_type.form_type,
                                state=models.Review.STATES.pending,
                                due_date=due_date
                            )
                        )
                if to_create:
                    models.Review.objects.bulk_create(to_create)
                    logs.append(f"{len(to_create)} {track} Reviews created for next stage")

        return '\n'.join(logs)
