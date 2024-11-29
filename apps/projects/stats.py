from django.db.models import Avg, Sum, Max
from django.db.models.functions import Coalesce
from django.utils import timezone

from misc.stats import DataTable


def get_project_stats():
    from proposals.models import ReviewCycle, Submission
    from projects.models import Project, Session, BeamTime, Reservation
    from scheduler.models import Mode, Schedule
    now = timezone.now().date()

    years = [
        y.year for y in
        ReviewCycle.objects.dates('start_date', 'year', order='ASC').distinct()
        if y.year <= now.year
    ]
    cycles = ReviewCycle.objects.exclude(close_date__gte=now)

    session_stats = {
        y: Session.objects.filter(start__year=y).with_shifts().aggregate(total=Sum('shifts'), max=Max('shifts'),
                                                                         average=Avg('shifts'))
        for y in years
    }
    beamtime_stats = {
        y: BeamTime.objects.filter(start__year=y).with_shifts().aggregate(total=Sum('shifts'), max=Max('shifts'),
                                                                          average=Avg('shifts'))
        for y in years
    }
    mode_stats = {
        y: Mode.objects.filter(start__year=y, schedule__state=Schedule.STATES.live).with_shifts().aggregate(
            total=Sum('shifts'), max=Max('shifts'), average=Avg('shifts')
        )
        for y in years
    }
    unavailable = {
        y: Reservation.objects.filter(cycle__start_date__year=y, kind__in=['', None]).aggregate(
            total=Coalesce(Sum('shifts'), 0))
        for y in years
    }

    tables = []
    tbl = [
        [''] + ['{}'.format(y) for y in years],
        ['Proposals'] + [Submission.objects.filter(cycle__start_date__year=yr).count() for yr in years],
        ['Projects'] + [Project.objects.filter(cycle__start_date__year=yr).count() for yr in years],
        ['Sessions'] + [Session.objects.filter(start__year=yr).count() for yr in years],
        ['Unique Users'] + [
            Session.objects.filter(start__year=yr).values_list('team__pk').distinct().count() for yr in years
        ],
        ['Usable Facility Shifts'] + [mode_stats[y]['total'] for y in years],
        ['Beamline Down Shifts'] + [unavailable[y]['total'] for y in years],
        ['Shifts Scheduled'] + [beamtime_stats[y]['total'] for y in years],
        ['Shifts Used'] + [session_stats[y]['total'] for y in years],
    ]

    dt = DataTable(tbl, heading='Availability and Usage by Year', max_cols=10)
    tables.append(dt)

    session_stats = {
        c: Session.objects.filter(
            start__gte=c.start_date, end__lte=c.end_date
        ).with_shifts().aggregate(total=Sum('shifts'), max=Max('shifts'), average=Avg('shifts'))
        for c in cycles
    }
    beamtime_stats = {
        c: BeamTime.objects.filter(
            start__gte=c.start_date, end__lte=c.end_date
        ).with_shifts().aggregate(total=Sum('shifts'), max=Max('shifts'), average=Avg('shifts'))
        for c in cycles
    }
    mode_stats = {
        c: Mode.objects.filter(
            start__gte=c.start_date, end__lte=c.end_date, schedule__state=Schedule.STATES.live
        ).with_shifts().aggregate(total=Sum('shifts'), max=Max('shifts'), average=Avg('shifts'))
        for c in cycles
    }
    unavailable = {
        c: Reservation.objects.filter(cycle=c, kind__in=['', None]).aggregate(total=Coalesce(Sum('shifts'), 0))
        for c in cycles
    }

    tbl = [
        [''] + ["{}".format(c.pk) for c in cycles],
        ['Proposals'] + [Submission.objects.filter(cycle=c).count() for c in cycles],
        ['Projects'] + [Project.objects.filter(cycle=c).count() for c in cycles],
        ['Sessions'] + [Session.objects.filter(start__gte=c.start_date, end__lte=c.end_date).count() for c in cycles],
        ['Unique Users'] + [
            Session.objects.filter(start__gte=c.start_date, end__lte=c.end_date).values_list(
                'team__pk').distinct().count() for c in cycles],
        ['Usable Facility Shifts'] + [mode_stats[c]['total'] for c in cycles],
        ['Beamline Down Shifts'] + [unavailable[c]['total'] for c in cycles],
        ['Shifts Scheduled'] + [beamtime_stats[c]['total'] for c in cycles],
        ['Shifts Used'] + [session_stats[c]['total'] for c in cycles],
    ]
    dt = DataTable(tbl, heading="Availability and Usage by Cycle", max_cols=10)
    tables.append(dt)

    return tables
