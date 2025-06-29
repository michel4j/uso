import sys

from django.core.management.base import BaseCommand

from ... import autodiscover, BaseCronJob
from ...models import BackgroundTask

autodiscover()


class Command(BaseCommand):
    help = 'Show all cron entries'
    can_import_settings = True

    def handle(self, *args, **options):
        out = "Current Cron Jobs:\n"
        for task in BackgroundTask.objects.all():
            out += f"{task.name:50s} {task.next_run()} \n"

        sys.stdout.write(out + '\n')
