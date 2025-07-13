

from datetime import timedelta

from django.conf import settings
from django.db.models import Case, Min, When, Q, BooleanField, Value, QuerySet, F
from django.utils import timezone, timesince

from proposals.models import Submission
from . import models
from . import utils
from isocron import BaseCronJob
from notifier import notify

SITE_URL = settings.SITE_URL


class NotifyProjects(BaseCronJob):
    """
    Notify applicants about the status of their projects and submissions.
    """
    run_at = "T00:30"  # Run every day at 00:30

    @staticmethod
    def process_cycle(cycle, projects, submissions):
        from proposals.models import Submission
        successful = projects.annotate(
            new=Case(When(Q(cycle=cycle), then=Value(1)), default=Value(0), output_field=BooleanField()),
            approved=Case(
                When(
                    Q(allocations__shifts__gt=0, allocations__beamline__flex_schedule=False) |
                    Q(allocations__beamline__flex_schedule=True) |
                    Q(submissions__track__require_call=False),
                    then=Value(1)
                ),
                default=Value(0),
                output_field=BooleanField()
            ),
            special=Min(Case(
                When(
                    Q(submissions__pool__is_default=True, submissions__track__require_call=False),
                    then=Value(1)
                ),
                default=Value(0),
                output_field=BooleanField()
            )),
        ).distinct()

        rejected = submissions.filter(approved=False).distinct()

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
                    f'{SITE_URL}{s.get_absolute_url()}' for s in project.submissions.all()
                ]),
                'project_url': f'{SITE_URL}{project.get_absolute_url()}',
                'allocations': project.allocations.filter(cycle=cycle),
            }
            notify.send([project.spokesperson], 'submission-success', level=notify.LEVELS.important, context=info)

        # Rejected:
        for submission in rejected:
            info = {
                'submission': submission,
                'cycle': cycle,
                'submission_urls': ", ".join([
                    f'{SITE_URL}{s.get_absolute_url()}' for s in [submission]
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
        cycle = ReviewCycle.objects.filter(alloc_date=yesterday, state=ReviewCycle.STATES.evaluation).first()
        if cycle:
            projects = models.Project.objects.filter(allocations__cycle=cycle)
            submissions = Submission.objects.filter(cycle=cycle, state=Submission.STATES.reviewed)
            self.process_cycle(cycle, projects, submissions)
            # toggle to scheduling after allocations are done and notified
            submissions.update(state=Submission.STATES.complete, modified=timezone.now())
            models.ReviewCycle.objects.filter(pk=cycle.pk).update(state=models.ReviewCycle.STATES.schedule)

        # Notify non-call projects the day after they are created
        cycle = ReviewCycle.objects.current().first()
        if cycle:
            projects = models.Project.objects.filter(
                allocations__cycle=cycle, created__date=yesterday
            ).exclude(submissions__track__require_call=True)
            submissions = Submission.objects.filter(cycle=cycle, state=Submission.STATES.reviewed)
            self.process_cycle(cycle, projects, submissions)
            submissions.update(state=Submission.STATES.complete, modified=timezone.now())

        return ""


class CreateCallProjects(BaseCronJob):
    """
    Create projects for all reviewed submissions in the current review cycle.
    Should be run before NotifyProjects.
    """
    run_at = "T00:15"  # Should run before Notify projects
    alloc_requests: QuerySet
    submissions: QuerySet

    def is_ready(self):
        from proposals.models import ReviewCycle, Submission
        from .models import AllocationRequest

        today = timezone.localtime(timezone.now()).date()

        # submissions in these cycles that require call
        self.submissions = Submission.objects.filter(
            cycle__alloc_date__lte=today, track__require_call=True, approved=True, project__isnull=True,
            state__gte=Submission.STATES.reviewed
        ).distinct()

        # allocation requests in these cycles that are submitted
        self.alloc_requests = AllocationRequest.objects.filter(
            cycle__alloc_date__lte=today, state=AllocationRequest.STATES.submitted,
            project__end_date__gte=F('cycle__end_date'),
        ).distinct()
        return self.submissions.exists() or self.alloc_requests.exists()

    def do(self):
        from proposals.models import ReviewCycle, Submission
        # create allocations for recently closed review cycles
        log = []

        if self.submissions.exists():
            for submission in self.submissions:
                utils.create_project(submission)
            log.append(f"Created projects for {self.submissions.count()} submissions.")

        # create allocations for allocation requests
        if self.alloc_requests.exists():
            count = 0
            for alloc_request in self.alloc_requests:
                spec = {
                    'facility': alloc_request.beamline.pk,
                    'justification': alloc_request.justification,
                    'procedure': alloc_request.procedure
                }
                utils.create_project_allocations(
                    alloc_request.project, spec, alloc_request.cycle,
                    shifts=0, shift_request=alloc_request.shift_request,
                )
                models.AllocationRequest.objects.filter(pk=alloc_request.pk).update(
                    state=models.AllocationRequest.STATES.complete)
                count += 1
            log.append(f"Renewed {count} project allocations from Allocation Requests")

        return "\n".join(log)


class CreateNonCallProjects(BaseCronJob):
    """
    Create projects for all approved reviewed non-call submissions in the current cycle.
    """
    run_every = "PT15M"
    submissions: QuerySet
    cycles: QuerySet

    def is_ready(self):
        from proposals.models import ReviewCycle, Submission
        # Handle non-call submissions and flexible beamlines
        today = timezone.localtime(timezone.now()).date()
        self.submissions = Submission.objects.filter(
            cycle__end_date__gte=today, track__require_call=False,
            state__gte=Submission.STATES.reviewed, approved=True, project__isnull=True
        ).distinct()
        self.cycles = ReviewCycle.objects.filter(open_date__lte=today, end_date__gte=today)

        return self.submissions.exists() or self.cycles.exists()

    def do(self):
        from proposals.models import ReviewCycle, Submission
        # Handle non-call submissions and flexible beamlines
        today = timezone.localtime(timezone.now()).date()

        log = []

        # create projects for non-call submissions
        if self.submissions.exists():
            for submission in self.submissions:
                utils.create_project(submission)
            log.append(f"Created {self.submissions.count()} projects for non-call review tracks")

        # create allocation objects for flexible beamlines every cycle, until expiry
        for cycle in self.cycles:
            next_cycle = ReviewCycle.objects.next(dt=cycle.start_date)
            if not next_cycle:
                continue

            # which projects on flexible beamlines which are still active next cycle do not have allocations yet
            flex_projects = models.Project.objects.exclude(cycle=next_cycle).filter(
                beamlines__flex_schedule=True, end_date__gte=next_cycle.end_date
            ).exclude(allocations__cycle=next_cycle).distinct()

            flex_allocations = models.Allocation.objects.filter(
                project__in=flex_projects, beamline__flex_schedule=True, cycle=cycle
            ).distinct()
            if flex_allocations.exists():
                for alloc in flex_allocations:
                    utils.create_allocation(
                        alloc.project, alloc.beamline, next_cycle,
                        procedure=alloc.procedure, justification=alloc.justification, shifts=0
                    )
                log.append(
                    f"Renewed {flex_allocations.count()} project allocations for flexible scheduling for cycle {next_cycle}"
                )

        return "\n".join(log)


class AutoSignOff(BaseCronJob):
    """
    Automatically sign off sessions that have not been signed off by the staff or spokesperson.
    """
    run_every = "PT4H"

    def do(self):
        from projects.models import Session
        now = timezone.localtime(timezone.now())
        prev_shift = timezone.localtime(timezone.now()) - timedelta(hours=8)
        pending = Session.objects.filter(state=Session.STATES.live, end__lte=prev_shift)

        for session in pending.all():
            bl_role = "admin:{}".format(session.beamline.acronym.lower())
            recipients = [bl_role]
            for u in {session.staff, session.spokesperson}:
                if not u.has_role(bl_role):
                    recipients.append(u)

            # Notify staff/spokesperson
            reason = f"Sign-off was expected {timesince.timesince(session.end)}"
            notify.send(recipients, 'auto-sign-off', level=notify.LEVELS.important, context={
                'session': session,
                'reason': reason
            })
            session.log('Auto Sign-Off on {}, Manual Sign-Off Overdue.'.format(now.strftime('%c')))
            session.state = Session.STATES.complete
            session.save()

        # cancel outstanding sessions on this beamline
        for session in Session.objects.filter(state=Session.STATES.ready, end__lte=prev_shift):
            session.log(f'Cancelled on {now.strftime("%c")}, Users did not sign-on as expected')
            session.state = Session.STATES.cancelled
            session.save()

        if pending.exists():
            return f"{pending.count()} expired sessions closed"
