from isocron import BaseCronJob
from datetime import date
import time
from . import utils
import os
from django.conf import settings
import json


class FetchBiosync(BaseCronJob):
    """
    Fetch the latest biosync data from the PDB and update the local database.
    """
    run_every = "P7D"

    def do(self):
        utils.fetch_and_update_depositions()


class FetchCitations(BaseCronJob):
    """
    Fetch the latest citation counts for articles published in the current month.
    """
    run_every = "P7D"

    def do(self):
        from publications import models
        logs = []
        year = date.today().year - 1
        for a in models.Publication.objects.filter(date__month=date.today().month, code__regex=r'^10\.'):
            cite_count = utils.get_citedby(a.code)
            if cite_count > 0 and cite_count != a.citations:
                logs += f'Updated citation count for {a.code}: {cite_count}\n'
                a.citations = cite_count
                a.history.append('Citation count updated on {0}'.format(date.today().isoformat()))
                a.save()
            time.sleep(0.1)
        return out


class UpdatePublications(BaseCronJob):
    """
    Update the meta-data for all articles published in the current month.
    """
    run_every = "P7D"

    def do(self):
        from publications import models
        out = ""
        for a in models.Article.objects.filter(date__gte=date.today()):
            info = utils.get_pub(a.code)
            models.Article.objects.filter(pk=a.pk).update(
                authors=info['authors'],
                title=info['title'],
                keywords=info['keywords'],
                volume=info['volume'],
                number=info['number'],
                date=info['date'])
            out += f'Updated meta-data for {a.code}'
            time.sleep(0.1)
        return out


class UpdateMetrics(BaseCronJob):
    """
    Update the SJR metrics for journals based on the latest SJR database.
    """
    run_every = "P3M"

    def do(self):
        from publications import models
        logs = []
        year = date.today().year - 1
        new_jmetrics = utils.fetch_journal_metrics(year)
        logs.append(f'Fetched {len(new_jmetrics)} journal metrics for year {year}')
        journal_metrics = utils.update_journal_metrics(year)
        logs.append(f'Updated {len(journal_metrics)} journal metrics for year {year}')
        pub_metrics = utils.update_publication_metrics(year)
        logs.append(f'Updated {len(pub_metrics)} publication metrics for year {year}')
        utils.update_funders()
        out = "\n".join(logs)
        return out
