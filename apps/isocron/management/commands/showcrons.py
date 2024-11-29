import sys

from django.core.management.base import BaseCommand

from ... import autodiscover, BaseCronJob
from ...models import JobLog

autodiscover()


class Command(BaseCommand):
    help = 'Show all cron entries'
    can_import_settings = True

    def handle(self, *args, **options):
        existing = BaseCronJob.get_all()
        orphaned = JobLog.objects.exclude(code__in=list(existing.keys()))
        ran = {j.code: j for j in JobLog.objects.all()}
        out = ""

        for k, job in list(existing.items()):
            if k in ran:
                out += "Existing Task: {0:35s} \t[{1}], Ran {2}, Status: {3}\n".format(k, job.describe(), ran[k].ran_at,
                                                                                       ran[k].get_state_display())
                # if ran[k].message:
                #    out += "------ log ------\n{0}\n-----------------\n".format(ran[k].message)
            else:
                out += "Existing Task: {0:35s} \t[{1}], Never ran\n".format(k, job.describe())

        for job in orphaned.all():
            out += "Orphaned Task: {0:35s}, Last seen {1}\n".format(job.code, job.ran_at)

        sys.stdout.write(out + '\n')
