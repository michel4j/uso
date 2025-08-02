import sys

from django.core.management.base import BaseCommand

from isocron import autodiscover, BaseCronJob
from isocron.models import BackgroundTask, TaskLog

autodiscover()


class Command(BaseCommand):
    help = 'Remove all log entries and reset task settings from file.'
    can_import_settings = True

    def handle(self, *args, **options):
        tasks = BaseCronJob.get_all()
        TaskLog.objects.all().delete()
        sys.stdout.write('Task log is clean\n')
        to_update = BackgroundTask.objects.all()
        for task in to_update:
            task.run_at = tasks[task.name].run_at
            task.run_every = tasks[task.name].run_every
            task.retry_after = tasks[task.name].retry_after
            task.keep_logs = tasks[task.name].keep_logs
            task.description = (tasks[task.name].__doc__ or "").replace('\n', ' ').strip()

        # Update the existing tasks with the new parameters
        BackgroundTask.objects.bulk_update(
            to_update, ['run_every', 'run_at', 'retry_after', 'keep_logs', 'description']
        )
