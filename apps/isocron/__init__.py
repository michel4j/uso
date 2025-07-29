from __future__ import annotations

import re
import threading
import traceback
from datetime import time, date, datetime, timedelta

import isodate
from django.utils import timezone

from misc.utils import load

ISO_PARSER = {
    re.compile(r'^T?\d{2}.*$'): isodate.parse_time,
    re.compile(r'^\d{4}-?\d{2}-?\d{2}$'): isodate.parse_date,
    re.compile(r'^\d{4}-?W\d{2}-?\d{1}$'): isodate.parse_date,
    re.compile(r'^\d{4}-?\d{3}$'): isodate.parse_date,
    re.compile(r'^\d{4}[\d-]+T\d{2}.*$'): isodate.parse_datetime,
    re.compile(r'^P.+$'): isodate.parse_duration,
}

KEEP_MESSAGES = 10


class CronJobMeta(type):
    def __init__(cls, *args, **kwargs):
        super(CronJobMeta, cls).__init__(*args, **kwargs)
        cls.code = ".".join([cls.__module__.split('.')[0], cls.__name__])
        if not hasattr(cls, 'plugins'):
            cls.plugins = {}
        else:
            cls.plugins[cls.code] = cls

    def get_all(self, *args, **kwargs):
        return {k: p(*args, **kwargs) for k, p in list(self.plugins.items())}

    def get_type(self, key):
        ft = self.plugins.get(key, None)
        if ft is not None:
            return ft()


class BaseCronJob(object, metaclass=CronJobMeta):
    keep_logs = KEEP_MESSAGES  # Number of logs to keep in the log
    run_every = None  # Duration or Time in ISO8601 format, if Time, it will run every day at that time.
    retry_after = "P1D"  # Duration in ISO8601 format to retry the job if it fails
    run_at = None  # Time string to run at ISO8601 format

    def do(self):
        """Work to do"""
        pass

    def is_ready(self) -> bool:
        """
        Return True or False if True, run if false, do not run. Can be used to check database conditions
        in addition to the time-based frequency. True by default. Instance variable can be set here and used
        in the do()
        """
        return True

    def run_thread(self, force=False):
        thread = threading.Thread(target=self.run, args=(force,), daemon=True)
        thread.start()
        return thread

    def run(self, force=False):
        from .models import BackgroundTask, TaskLog
        ready_to_run = self.is_ready()  # make sure is_ready is always called
        if force or ready_to_run:
            now = timezone.localtime(timezone.now())
            task = BackgroundTask.objects.get(name=self.code)
            log = task.save_log(state=TaskLog.StateType.running, message=f"Running cron job since {now.isoformat()}")
            try:
                out = self.do()
                now = timezone.localtime(timezone.now())
                TaskLog.objects.filter(pk=log.pk).update(
                    state=TaskLog.StateType.success,
                    message=out or "Job completed successfully",
                    modified=now
                )
                return 1
            except Exception as e:
                out = f"Error running cronjob: {e}\n"
                out += traceback.format_exc()
                now = timezone.localtime(timezone.now())
                TaskLog.objects.filter(pk=log.pk).update(
                    state=TaskLog.StateType.failed,
                    message=out,
                    modified=now
                )
                return -1
        return 0


def parse_iso(ts: str | None) -> datetime | time | date | timedelta | None:
    """
    Parse an ISO 8601 formatted string into a timezone-aware datetime object or timedelta.

    :param ts: a string or None, the ISO 8601 formatted string to parse.
    :return:
    """
    if not ts:
        return None

    for patt, parser in ISO_PARSER.items():
        if patt.match(ts):
            try:
                # Try to parse the string using the appropriate parser
                t = parser(ts)
            except isodate.ISO8601Error as e:
                continue
            return t
    return None


def autodiscover():
    """
    Discover and load all cron jobs defined in the isocron app and create BackgroundTask entries for them
    if one does not exist. Also remove any BackgroundTask entries that do not have a corresponding cron job.

    """
    try:
        from .models import BackgroundTask
        load('cron')
        tasks = BaseCronJob.get_all()
        existing = set(BackgroundTask.objects.values_list('name', flat=True))
        new_tasks = set(tasks.keys()) - existing
        to_create = [
            BackgroundTask(
                name=name, run_every=tasks[name].run_every, run_at=tasks[name].run_at,
                retry_after=tasks[name].retry_after, keep_logs=tasks[name].keep_logs,
                description=(tasks[name].__doc__ or "").replace('\n', ' ').strip()
            )
            for name in new_tasks
        ]
        if to_create:
            BackgroundTask.objects.bulk_create(to_create)

        to_remove = existing - set(tasks.keys())
        if to_remove:
            BackgroundTask.objects.filter(name__in=list(to_remove)).delete()

    except Exception:
        # If there is an error, we do not want to crash the server, just log it
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Cron job autodiscover failed. Please retry after migrations.")

