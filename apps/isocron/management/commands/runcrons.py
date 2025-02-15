import sys

from django.core.management.base import BaseCommand

from isocron import autodiscover, BaseCronJob

autodiscover()


class Command(BaseCommand):
    args = "<jobName> <jobName>"
    help = 'Run all Cron Jobs that need running or only the ones specified'
    can_import_settings = True

    def add_arguments(self, parser):
        parser.add_argument('--force',
                            action="store_true",
                            dest="force",
                            default=False,
                            help="Force jobs to run this time")
        parser.add_argument('jobs', nargs='*', type=str)

    def handle(self, *args, **options):
        jobs = BaseCronJob.get_all().items()
        out = ""
        for name, cron_job in jobs:
            if options.get('jobs') and name not in options.get('jobs', []):
                continue
            code = cron_job.run(force=options.get('force'))

            if options.get('verbosity', 1) > 0:
                if code == 0:
                    out += f'{cron_job.job_log.code} (Skipped)\n'
                elif code == 1:
                    out += f'{cron_job.job_log.code} (Success)\n'
                else:
                    out += f'{cron_job.job_log.code} (Failed)\n'
                sys.stdout.write(out)
