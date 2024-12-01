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
        parser.add_argument('--verbose',
                            action="store_true",
                            dest="verbose",
                            default=False,
                            help="Be very noisy")

    def handle(self, *args, **options):
        skipped = []
        job_threads = {}
        jobs = BaseCronJob.get_all().items()
        out = ""
        for name, cron_job in jobs:
            if args and name not in args:
                continue
            thread = cron_job.run_thread(force=options.get('force'))
            if thread:
                job_threads[cron_job] = thread
            else:
                skipped.append(cron_job)

        for job, thread in job_threads.items():
            thread.join()
            out += '{} ({})\n'.format(job.job_log.code, job.job_log.get_state_display())

        for job in skipped:
            out += '{} ({})\n'.format(job.job_log.code, 'Skipped')

        if options.get('verbose'):
            sys.stdout.write(out)
