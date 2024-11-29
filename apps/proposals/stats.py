from django.utils import timezone

from misc.stats import DataTable


def get_proposal_stats():
    from . import models
    now = timezone.now().date()
    years = [
        y.year for y in
        models.ReviewCycle.objects.dates('start_date', 'year', order='ASC').distinct()
        if y.year <= now.year
    ]
    cycles = models.ReviewCycle.objects.exclude(close_date__gte=now)

    tables = []
    tbl = [
        [''] + [y for y in years],
        ['Proposals'] + [models.Submission.objects.filter(cycle__start_date__year=yr).count() for yr in years],
        ['Participating Facilities'] + [
            models.FacilityConfig.objects.active(year=yr).distinct().count() for yr in years
        ],
        ['External Reviewers'] + [models.Reviewer.objects.filter(cycles__start_date__year=yr).distinct().count() for yr
                                  in years],
        ['Submitters'] + [models.Submission.objects.filter(cycle__start_date__year=yr).values_list(
            'proposal__spokesperson').distinct().count() for yr in years],
    ]
    dt = DataTable(tbl, heading="Proposal Statistics by Year", max_cols=10)
    tables.append(dt)

    tbl = [
        [''] + [c.pk for c in cycles],
        ['Proposals'] + [c.num_submissions() for c in cycles],
        ['Participating Facilities'] + [c.num_facilities() for c in cycles],
        ['External Reviewers'] + [c.reviewers.count() for c in cycles],
        ['Submitters'] + [
            models.Submission.objects.filter(cycle=c).values_list('proposal__spokesperson').distinct().count() for c in
            cycles],
    ]
    dt = DataTable(tbl, heading="Proposal Statistics by Cycle", max_cols=10)
    tables.append(dt)

    return tables


def proposals_summary():
    pass
