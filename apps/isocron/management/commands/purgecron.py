import sys

from django.core.management.base import BaseCommand

from ... import autodiscover
from ...models import TaskLog

autodiscover()


class Command(BaseCommand):
    help = 'Remove all log entries for cron jobs.'
    can_import_settings = True

    def handle(self, *args, **options):
        TaskLog.objects.all().delete()
        sys.stdout.write('Task log is clean\n')
