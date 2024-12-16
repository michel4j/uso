

from datetime import timedelta

from django.conf import settings
from django.db.models import Case, Min, When, Q, BooleanField, Value
from django.utils import timezone, timesince

from . import models
from . import utils
from isocron import BaseCronJob
from notifier import notify

SITE_URL = settings.SITE_URL


class NotifyProjects(BaseCronJob):
    run_at = ["00:30"]

    @staticmethod
    def process_cycle(cycle, projects, submissions):
        from proposals.models import Submission
        successful = projects.annotate(
            new=Case(When(Q(cycle=cycle), then=Value(1)), default=Value(0), output_field=BooleanField()),
            approved=Case(
                When(
                    Q(allocations__shifts__gt=0, allocations__beamline__flex_schedule=False) |
                    Q(allocations__beamline__flex_schedule=True) |
                    Q(submissions__track__special=True),
                    then=Value(1)
                ),
                default=Value(0),
                output_field=BooleanField()
            ),
            special=Min(Case(
                When(
                    Q(submissions__kind=Submission.TYPES.user, submissions__track__special=True),
                    then=Value(1)
                ),
                default=Value(0),
                output_field=BooleanField()
            )),
        ).distinct()

        rejected = submissions.filter(project__isnull=True).distinct()

        # Success:
        for project in successful:

            # only notify flex allocations once
            if project.cycle != cycle and not project.allocations.filter(cycle=cycle).exclude(
                    beamline__flex_schedule=True).distinct().exists():
                continue

            info = {
                'project': project,
                'cycle': cycle,
                'submission_urls': ", ".join([
                    '{}{}'.format(SITE_URL, s.get_absolute_url()) for s in project.submissions.all()
                ]),
                'project_url': '{}{}'.format(SITE_URL, project.get_absolute_url()),
                'allocations': project.allocations.filter(cycle=cycle),
            }
            notify.send([project.spokesperson], 'submission-success', level=notify.LEVELS.important, context=info)

        # Rejected:
        for submission in rejected:
            info = {
                'submission': submission,
                'cycle': cycle,
                'submission_urls': ", ".join([
                    '{}{}'.format(SITE_URL, s.get_absolute_url()) for s in [submission]
                ]),
            }
            notify.send(
                [submission.proposal.spokesperson], 'submission-fail', level=notify.LEVELS.important, context=info
            )

    def do(self):
        from proposals.models import ReviewCycle, Submission
        today = timezone.localtime(timezone.now()).date()
        yesterday = today - timedelta(days=1)

        # Send notifications for recently completed allocations
        # cycle = ReviewCycle.objects.get(pk=24)
        cycle = ReviewCycle.objects.filter(alloc_date=yesterday, state=ReviewCycle.STATES.evaluation).first()
        if cycle:
            projects = models.Project.objects.filter(allocations__cycle=cycle)
            submissions = Submission.objects.filter(cycle=cycle, state=Submission.STATES.reviewed)
            self.process_cycle(cycle, projects, submissions)
            # toggle to scheduling after allocations are done and notified
            submissions.update(state=Submission.STATES.complete, modified=timezone.now())
            models.ReviewCycle.objects.filter(pk=cycle.pk).update(state=models.ReviewCycle.STATES.schedule)

        # Notify RA projects the day after they are created
        cycle = ReviewCycle.objects.current().first()
        if cycle:
            projects = models.Project.objects.filter(
                allocations__cycle=cycle, created__date=yesterday
            ).exclude(submissions__track__special=False)
            submissions = Submission.objects.filter(cycle=cycle, state=Submission.STATES.reviewed)
            self.process_cycle(cycle, projects, submissions)
            submissions.update(state=Submission.STATES.complete, modified=timezone.now())

        return ""


class CreateProjects(BaseCronJob):
    run_at = ["00:15"]  # Should run before Notify projects

    def do(self):
        from proposals.models import ReviewCycle, Submission
        today = timezone.localtime(timezone.now()).date()

        # create allocations for recently closed review cycles
        cycle = ReviewCycle.objects.filter(alloc_date=today, state=ReviewCycle.STATES.review).first()
        # cycle = ReviewCycle.objects.get(pk=25)
        log = []
        if cycle:
            # general user access
            submissions = cycle.submissions.exclude(track__special=True).filter(
                state=Submission.STATES.reviewed, project__isnull=True)
            expiry = (cycle.start_date.replace(year=cycle.start_date.year + 2))
            for submission in submissions:
                utils.create_project(submission)
            log.append("Processed {} Peer-Reviewed submissions for cycle {}".format(submissions.count(), cycle))

            # create allocations for allocation requests
            count = 0
            for alloc_request in cycle.allocation_requests.filter(state=models.AllocationRequest.STATES.submitted):
                spec = {
                    'facility': alloc_request.beamline.pk,
                    'justification': alloc_request.justification,
                    'procedure': alloc_request.procedure
                }
                # FIXME: Score adjustments ??
                utils.create_project_allocations(
                    alloc_request.project, spec, alloc_request.cycle,
                    shifts=0, shift_request=alloc_request.shift_request,
                )
                models.AllocationRequest.objects.filter(pk=alloc_request.pk).update(
                    state=models.AllocationRequest.STATES.complete)
                count += 1
            log.append("Created {} allocations from Allocation Requests for cycle {}".format(count, cycle))
            ReviewCycle.objects.filter(pk=cycle.pk).update(state=ReviewCycle.STATES.evaluation)

        # convert rapid access proposals to projects
        cycle = ReviewCycle.objects.current().first()
        if cycle is None:
            log.append("No current cycle found")
            return "\n".join(log)

        submissions = Submission.objects.filter(
            cycle__pk__gte=cycle.pk, track__special=True, state=Submission.STATES.reviewed, project__isnull=True
        ).distinct()
        for submission in submissions:
            utils.create_project(submission)
        log.append("Created {} projects from Rapid-Access submissions".format(submissions.count()))

        # create allocation objects for flexible beamlines every cycle, until expiry
        next_cycle = ReviewCycle.objects.next()

        # projects on flexible beamlines which are still active next cycle but which do not have allocations for it yet
        flex_projects = models.Project.objects.exclude(cycle=next_cycle).filter(
            beamlines__flex_schedule=True, end_date__gte=next_cycle.end_date
        ).exclude(allocations__cycle=next_cycle).distinct()

        flex_allocations = models.Allocation.objects.filter(
            project__in=flex_projects, beamline__flex_schedule=True, cycle=cycle).distinct()

        for alloc in flex_allocations:
            utils.create_allocation(alloc.project, alloc.beamline, next_cycle,
                                    procedure=alloc.procedure, justification=alloc.justification, shifts=0)
        log.append(
            "Created {} allocations for flexible scheduling for cycle {}".format(flex_allocations.count(), next_cycle))

        return "\n".join(log)


class AutoSignOff(BaseCronJob):
    run_at = ["08:00", "16:00", "00:00"]

    def do(self):
        from projects.models import Session
        now = timezone.localtime(timezone.now())
        prev_shift = timezone.localtime(timezone.now()) - timedelta(hours=8)
        pending = Session.objects.filter(state=Session.STATES.live, end__lte=prev_shift)

        for session in pending.all():
            bl_role = "beamline-admin:{}".format(session.beamline.acronym.lower())
            recipients = [bl_role]
            for u in {session.staff, session.spokesperson}:
                if not u.has_role(bl_role):
                    recipients.append(u)

            # Notify staff/spokesperson
            reason = "Sign-off was expected {}".format(timesince.timesince(session.end))
            notify.send(recipients, 'auto-sign-off', level=notify.LEVELS.important, context={
                'session': session,
                'reason': reason
            })
            session.log('Auto Sign-Off on {}, Manual Sign-Off Overdue.'.format(now.strftime('%c')))
            session.state = Session.STATES.complete
            session.save()

        # cancel outstanding sessions on this beamline
        for session in Session.objects.filter(state=Session.STATES.ready, end__lte=prev_shift):
            session.log('Cancelled on {}, Users did not sign-on as expected'.format(now.strftime('%c')))
            session.state = Session.STATES.cancelled
            session.save()

        if pending.exists():
            return "{} expired sessions closed".format(pending.count())
