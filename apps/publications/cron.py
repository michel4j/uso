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
        utils.fetch_pdbs()


class FetchCitations(BaseCronJob):
    """
    Fetch the latest citation counts for articles published in the current month.
    """
    run_every = "P1M"

    def do(self):
        from publications import models
        out = ""
        for a in models.Article.objects.filter(date__month=date.today().month):
            cite_count = utils.get_citedby(a.code)
            if cite_count > 0 and cite_count != a.citations:
                out += 'Updated citation count for {0}: {1}\n'.format(a.code, cite_count)
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
        out = ""
        last_year = date.today().year - 1
        sjrdb_list = list(utils.SJRDB.values())

        if not sjrdb_list and f'Total Docs. ({last_year})' in sjrdb_list[0]:
            return "SJR database is up-to-date on {0}".format(date.today())

        sjrdb = utils.get_sjr(last_year)
        if sjrdb:
            metrics_dir = os.path.join(settings.LOCAL_DIR, 'metrics')
            os.makedirs(metrics_dir, exist_ok=True)
            with open(os.path.join(settings.LOCAL_DIR, 'metrics', 'sjr.json'), 'w') as fobj:
                json.dump(sjrdb, fobj)

            for issn, record in list(sjrdb.items()):
                scores = {
                    'sjr': record['SJR'],
                    'ifactor': record['Cites / Doc. (2years)'],
                    'hindex': int(record['H index']),
                    'score_date': date.today()
                }
                if issn in utils.IFDB:
                    scores['ifactor'] = utils.IFDB[issn][sorted(utils.IFDB[issn].keys())[-4]]
                models.Journal.objects.filter(codes__icontains=issn).update(**scores)
            utils.load_metrics()
            out += 'Updated Journal SJR meta-data on {0}'.format(date.today())
        return out
