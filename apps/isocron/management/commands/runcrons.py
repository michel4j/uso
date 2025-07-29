import sys

from django.core.management.base import BaseCommand
from isocron.models import BackgroundTask
from isocron import autodiscover

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
        tasks = BackgroundTask.objects.all()
        if options.get('jobs'):
            tasks = tasks.filter(name__in=options.get('jobs'))

        out = ""
        for task in tasks:
            if task.is_due() or options.get('force', False):
                result = task.run_job(force=options.get('force', False))
            else:
                result = 0

            if options.get('verbosity', 0) > 0:
                if result == 0:
                    out += f'{task.name:30s} ...Skipped\n'
                elif result == 1:
                    out += f'{task.name:30s} ...Success\n'
                else:
                    out += f'{task.name:30s} ...Failed\n'
                sys.stdout.write(out)
