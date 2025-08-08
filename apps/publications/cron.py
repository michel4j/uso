
from django.db.models import QuerySet, Q, Value, IntegerField
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models.functions import Cast
from django.utils import timezone

from isocron import BaseCronJob
from . import utils


class FetchPDBEntries(BaseCronJob):
    """
    Fetch the latest Deposition data from the PDB and update the local database.
    """
    run_every = "P10D"

    def do(self):
        out = utils.fetch_and_update_pdbs()
        logs = [
            f'Fetched {out["created"]} new PDB entries",'
            f'Updated {out["updated"]} existing entries.'
        ]
        return '\n'.join(logs)


class UpdatePDBReferences(BaseCronJob):
    """
    Fetch the latest CrossRef data for PDB entries
    """
    run_every = "P5D"

    pending: QuerySet

    def is_ready(self):
        from .models import Publication
        self.pending = Publication.objects.filter(
            kind=Publication.TYPES.pdb, pdb_doi__isnull=False, reference__isnull=True
        )

        return self.pending.exists()

    def do(self):
        out = utils.update_pdb_references(self.pending)
        return f"Added {out['references']} references to {out['pdbs']} PDB entries"


class UpdateArticleMetrics(BaseCronJob):
    """
    Fetch the latest citation counts for articles published in the current month.
    """
    run_every = "P14D"

    def do(self):
        # FIXME: some older metrics may be missed if article was published before the last run but only added recently
        from publications import utils
        out = utils.update_publication_metrics()
        logs = [
            f'Updated {out["updated"]} article metrics.',
            f'Created {out["created"]} new metrics for articles.'
        ]
        return '\n'.join(logs)


class UpdateJournalMetrics(BaseCronJob):
    """
    Update the SJR metrics for journals based on the latest SJR database.
    """
    run_every = "P3M"
    missing_years: list[int]

    def is_ready(self):
        from publications import models
        spans = models.Journal.objects.aggregate(
            article_years=ArrayAgg(
                Cast('articles__date__year', output_field=IntegerField()),
                filter=Q(articles__date__year__isnull=False),
                distinct=True,
                default=Value([])
            ),
            metrics_years=ArrayAgg(
                Cast('metrics__year', output_field=IntegerField()),
                filter=Q(metrics__year__isnull=False),
                distinct=True,
                default=Value([])
            ),
        )
        article_years = spans['article_years']
        min_year = min(article_years)
        max_year = max(article_years)
        all_years = set(range(min_year, max_year + 1))
        metrics_years = set(spans['metrics_years'])
        self.missing_years = list(sorted(all_years - metrics_years))
        return len(self.missing_years) > 0

    def do(self):
        from publications import utils
        logs = []

        for year in self.missing_years:
            out = utils.update_journal_metrics(year=year)
            logs.extend([
                f'Created {out["created"]} new journal metrics for year {year}.',
                f'Updated {out["updated"]} existing journal metrics for year {year}.'
            ])
        return '\n'.join(logs)
