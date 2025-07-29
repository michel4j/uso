from __future__ import annotations

import isodate
from django.db import models
from datetime import datetime, timedelta, time

from django.db.models import TextChoices
from django.utils.timesince import timesince
from model_utils.models import TimeStampedModel
from django.utils import timezone
from isocron import parse_iso, BaseCronJob, utils

JOB_TIME_RESOLUTION = 600       # maximum resolution for job times in seconds (10 minutes)


def calculate_run_time(run_at: str, dt: datetime = None) -> datetime:
    """
    Convert an ISO 8601 time strings to a datetime object for the given day.
    :param run_at: ISO 8601 time strings or durations (e.g., "12:00", "T14:30", "P2D1H").
    :param dt: Optional datetime to use for the reference date and time, defaults to now.
    """
    now = timezone.localtime(dt if dt else timezone.now())
    run_time = parse_iso(run_at)
    if isinstance(run_time, timedelta):
        # If run_at is a duration, calculate the time from now
        run_time = now + run_time
    elif isinstance(run_time, time):
        # If run_at is a time, combine it with reference datetime
        run_time = now.replace(
            hour=run_time.hour,
            minute=run_time.minute,
            second=run_time.second,
            microsecond=run_time.microsecond
        )
    elif isinstance(run_time, datetime):
        # If run_at is a datetime, ensure it is timezone-aware
        if run_time.tzinfo is None:
            run_time = timezone.make_aware(run_time, timezone.get_current_timezone())
    else:
        # Generate a time way into the future
        run_time = datetime(now.year + 100, 1, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())

    return run_time


class TaskLogManager(models.Manager):
    def running(self):
        return self.filter(state=TaskLog.StateType.running)

    def success(self):
        return self.filter(state=TaskLog.StateType.success)

    def failed(self):
        return self.filter(state=TaskLog.StateType.failed)


class BackgroundTask(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    keep_logs = models.IntegerField(default=10, help_text="Number of logs to keep in the log")
    run_every = models.CharField(max_length=50, blank=True, null=True, help_text="ISO 8601 Time or Duration String")
    run_at = models.CharField(max_length=50, null=True, help_text="ISO 8601 Time String")
    retry_after = models.CharField(max_length=50, blank=True, null=True, help_text="ISO 8601 Duration")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.task()

    def task(self) -> str:
        """
        Get the task name without the module prefix.
        :return: The task name as a string.
        """
        return self.name.split('.')[-1]
    task.sort_field = 'name'
    task.short_description = 'Task'
    task.allow_tags = True

    def app(self) -> str:
        """
        Get the application name from the task name.
        :return: The application name as a string.
        """
        return self.name.split('.')[0]
    app.sort_field = 'name'
    app.short_description = 'App'
    app.allow_tags = True

    def last_ran(self):
        """
        Get the last run status of the task based on the latest log entry.
        :return: The last run time as a datetime object or None if no logs exist.
        """
        last_log = self.last_log()
        return "Never" if not last_log else f"{timesince(last_log.modified)} ago"
    last_ran.sort_field = 'logs__modified'

    def clean_logs(self):
        """
        Clean up old logs based on keep_logs setting.
        If keep_logs is 0, or not set, keep everything.
        """
        if self.keep_logs > 0:
            logs = self.logs.order_by('-created')
            if logs.count() > self.keep_logs:
                self.logs.filter(pk__in=logs[self.keep_logs:].values_list('pk', flat=True)).delete()

    def last_log(self) -> 'TaskLog':
        """
        Get the last log entry for this task.
        :return: The last TaskLog instance or None if no logs exist.
        """
        return self.logs.order_by('-created').first()

    def run_job(self, force=False):
        """
        Run the job associated with this task.
        This method should be overridden in subclasses to implement the actual job logic.
        :param force: If True, force the job to run even if conditions are not met.
        """
        cron_job = BaseCronJob.get_type(self.name)
        if cron_job:
            return cron_job.run(force=force)
        return 0

    def save_log(self, message: str, state: 'TaskLog.StateType') -> 'TaskLog':
        """
        Save a log entry for this task.
        :param message: The log message to save.
        :param state: The state of the task (running, success, failed).
        :return: The created TaskLog instance.
        """

        log = TaskLog.objects.create(task=self, message=message, state=state)
        self.clean_logs()
        return log

    def next_run(self) -> datetime | None:
        """
        Calculate the next time this task should run based on run_every and run_at.
        :return: A datetime object representing the next run time.
        """

        last_log = self.last_log()
        prev_time = None if not last_log else last_log.created

        return utils.next_run_time(self.run_every, self.run_at,last_time=prev_time)

    def is_due(self) -> bool:
        """
        Check if the task is due to run based on run_every, run_at and last_log.
        """
        next_time = self.next_run()
        last_log = self.last_log()
        now = timezone.localtime(timezone.now())
        retry_time = parse_iso(self.retry_after)

        last_failed = (
            last_log and last_log.state == TaskLog.StateType.failed
            if last_log else False
        )
        if not next_time:
            return False
        elif next_time < now and not last_failed:
            return True
        elif last_failed and retry_time:
            return (now - last_log.created) >= retry_time
        elif not last_log:
            return True
        return False

    class Meta:
        app_label = 'isocron'
        verbose_name = 'Background Task'
        verbose_name_plural = 'Background Tasks'


class TaskLog(TimeStampedModel):
    class StateType(TextChoices):
        running = 'running', 'Running'
        success = 'success', 'Success'
        failed = 'failed', 'Failed'

    task = models.ForeignKey(BackgroundTask, related_name='logs', on_delete=models.CASCADE)
    message = models.TextField(blank=True, null=True, help_text="Log message")
    state = models.CharField(max_length=20, choices=StateType.choices, default=StateType.failed)

    def __str__(self):
        return f'{self.task.name} - {self.created.isoformat()}'

