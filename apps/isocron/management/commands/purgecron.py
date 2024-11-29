import sys

from django.core.management.base import BaseCommand

from ... import autodiscover, BaseCronJob
from ...models import JobLog

autodiscover()


class Command(BaseCommand):
    help = 'Remove all orphaned cron entries from database'
    can_import_settings = True

    def handle(self, *args, **options):
        existing = list(BaseCronJob.get_all().keys())
        qset = JobLog.objects.exclude(code__in=existing)
        total = qset.count()
        if total > 0:
            out = 'Removing {0} orphaned cronjob(s) from job log: '.format(total)
            out += ', '.join([j.code for j in qset])
            qset.delete()
        else:
            out = 'Job log is clean.'
        sys.stdout.write(out + '\n')
