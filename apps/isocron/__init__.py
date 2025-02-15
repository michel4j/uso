import bisect
import re
import threading
import traceback
from datetime import time, date, datetime

import aniso8601
import pytz
from django.conf import settings
from django.utils import timezone

from misc.utils import load

ISO_PARSER = {
    re.compile(r'^\d{2}:\d{2}.*$'): aniso8601.parse_time,
    re.compile(r'^\d{4}-\d{2}-\d{2}$'): aniso8601.parse_date,
    re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}.*$'): aniso8601.parse_datetime,
}

KEEP_MESSAGES = 10
TEST_FREQ = 10 * 60  # Number of seconds between successive testing of cron jobs. This is the frequency of the cron job


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
    run_every = None  # Duration in ISO8601 format
    retry_after = None  # If failure retry after minutes
    run_at = []  # List of time strings to run at ISO8601 format

    def do(self):
        """Work to do"""
        pass

    def condition(self):
        """Return True or False if True, run if false, do not run. Can be used to check database conditions
         in addition to the time based frequency. True by default"""
        return True

    def describe(self):
        return "EVERY: {0}, AT: {1}, RETRY: {2}".format(self.run_every, self.run_at, self.retry_after)

    def run_thread(self, force=False):
        thread = threading.Thread(target=self.run, args=(force,), daemon=True)
        thread.start()
        return thread

    def run(self, force=False):
        from .models import JobLog
        if not (self.ready() and self.condition() or force):
            return 0

        now = timezone.localtime(timezone.now())
        msgs = []
        try:
            JobLog.objects.filter(pk=self.job_log.pk).update(state=JobLog.STATES.running)
            out = self.do()
            out_msg = "{}\n".format(out) if out else ""
            messages = [
                           "\n=============== SUCCESS ({}) ===============\n{}".format(now.isoformat(), out_msg)
                       ] + msgs
            messages = messages if len(messages) < KEEP_MESSAGES else messages[-KEEP_MESSAGES:]
            JobLog.objects.filter(pk=self.job_log.pk).update(state=JobLog.STATES.success,
                                                             message="\n$$\n".join(messages), ran_at=now)
            return 1
        except Exception as e:
            out = f"Error running cronjob: {e}"
            out += traceback.format_exc()
            out_msg = "{}\n".format(out) if out else ""
            messages = [
                           "\n=============== FAILURE ({}) ===============\n{}".format(now.isoformat(), out)
                       ] + msgs
            messages = messages if len(messages) < KEEP_MESSAGES else messages[-KEEP_MESSAGES:]
            JobLog.objects.filter(pk=self.job_log.pk).update(state=JobLog.STATES.failed,
                                                             message="\n$$\n".join(messages), ran_at=now)
            return -1

    def ready(self):
        """ Check if job is ready to run """
        from .models import JobLog

        try:
            self.job_log = JobLog.objects.get(code=self.code)
        except JobLog.DoesNotExist:
            self.job_log = JobLog.objects.create(code=self.code)

        # do not run job if it is running already
        if self.job_log.state == self.job_log.STATES.running:
            return False

        now = timezone.localtime(timezone.now())
        ran_ago = (now - self.job_log.ran_at)

        if self.job_log.state == self.job_log.STATES.never:
            return True

        # if both run_every and run_at, require both conditions to be met.
        should_run = True
        if self.run_every:
            should_run = False
            repeat_dur = aniso8601.parse_duration(self.run_every)
            if ran_ago > repeat_dur:
                should_run = True
            elif self.retry_after and self.job_log.state != self.job_log.STATES.success:
                retry_dur = aniso8601.parse_duration(self.retry_after)
                if ran_ago > retry_dur:
                    should_run = True

        if should_run and self.run_at:
            # run if there is a requested time between current time and last ran time
            run_times = sorted([_f for _f in [parse_iso(ts) for ts in self.run_at] if _f])
            ran_index = bisect.bisect_left(run_times, self.job_log.ran_at)
            now_index = bisect.bisect_left(run_times, now)
            return now_index - ran_index > 0
        else:
            return should_run


def parse_iso(ts):
    now = timezone.now()
    for patt, parser in list(ISO_PARSER.items()):
        if patt.match(ts):
            t = parser(ts)
            if isinstance(t, datetime):
                pass
            elif isinstance(t, date):
                t = datetime.combine(t, time(12, 0))
            elif isinstance(t, time):
                t = datetime.combine(now.date(), t)
            return timezone.make_aware(t, pytz.timezone(settings.TIME_ZONE))
    return None


def autodiscover():
    load('cron')
