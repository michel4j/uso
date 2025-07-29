from __future__ import annotations

from datetime import datetime, timedelta, time
from django.utils import timezone
from isocron import parse_iso


def next_run_time(
    run_every: str,
    run_at: str,
    last_time: datetime = None
) -> datetime | None:
    """
    Calculate the next run time based on the provided parameters.
    :param run_every: iso string representing the interval to run the task, e.g., "PT1H" for every hour or "T12:00"
    for every day at noon.
    :param run_at: iso string representing the specific time to run the task, e.g., "T12:00" for noon every day.
    :param last_time: datetime of the last run. or None if it has never run.
    :return: Next run time as a datetime object or None if no run is scheduled.
    """
    if not run_every and not run_at:
        return None

    current_time = timezone.localtime(timezone.now())
    at_time = None if not run_at else parse_iso(run_at)
    every_obj = None if not run_every else parse_iso(run_every)
    every_time = every_duration = None

    if isinstance(every_obj, time):
        every_time = every_obj
    else:
        every_duration = every_obj

    prev_time = last_time

    if every_time:
        # If run_every is a time, calculate the next run time for today
        next_time = current_time.replace(
            hour=every_time.hour,
            minute=every_time.minute,
            second=every_time.second,
            microsecond=every_time.microsecond
        )
        if next_time <= prev_time:
            next_time += timedelta(days=1)
    elif every_duration:
        # If run_every is a duration, add it to previous run time
        if not prev_time:
            next_time = current_time
        else:
            next_time = prev_time + every_duration
        if at_time and every_duration > timedelta(days=1):
            # for durations longer than a day, adjust the time to run at otherwise ignore it
            next_time = next_time.replace(
                hour=at_time.hour,
                minute=at_time.minute,
                second=at_time.second,
                microsecond=at_time.microsecond
            )
    elif at_time:
        # run at this time every day
        next_time = current_time.replace(
            hour=at_time.hour,
            minute=at_time.minute,
            second=at_time.second,
            microsecond=at_time.microsecond
        )
        if next_time <= prev_time:
            next_time += timedelta(days=1)
    else:
        next_time = None

    return timezone.localtime(next_time)
