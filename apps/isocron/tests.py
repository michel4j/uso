import unittest
from unittest.mock import patch
from datetime import datetime
from django.utils import timezone
from django.test import TestCase
from isocron.models import BackgroundTask, TaskLog
from isocron import autodiscover, BaseCronJob, parse_iso
from isocron.utils import next_run_time


class TestSuccess(BaseCronJob):
    run_every = "P7D"
    run_at = "12:00"
    keep_logs = 2

    def do(self):
        return "Test success"


class TestFailure(BaseCronJob):
    run_every = "P2D"
    retry_after = "PT1H"
    keep_logs = 1

    def do(self):
        raise Exception("Test failure")


class BackgroundTaskModelTests(TestCase):

    def setUp(self):
        autodiscover()

    def test_autodiscover(self):
        task_names = set(BackgroundTask.objects.values_list('name', flat=True))
        self.assertTrue({'isocron.TestSuccess', 'isocron.TestFailure'} & task_names, "Test Tasks not discovered")
        task1 = BackgroundTask.objects.get(name="isocron.TestSuccess")
        task2 = BackgroundTask.objects.get(name="isocron.TestFailure")
        self.assertEqual(task1.run_every, "P7D", "Run every for TestSuccess should be P7D")
        self.assertEqual(task1.run_at, "12:00", "Run at for TestSuccess should be '12:00'")
        self.assertEqual(task2.retry_after, "PT1H", "Run every for TestFailure should be PT1H")
        self.assertEqual(task2.keep_logs, 1, "Keep logs for TestFailure should be 1")

    def test_autodiscover_tasks(self):
        tasks = BackgroundTask.objects.all()
        cron_jobs = BaseCronJob.get_all()
        cron_job_names = set(cron_jobs.keys())
        self.assertGreater(len(tasks), 0, "No BackgroundTask entries created by autodiscover")
        for task in tasks:
            self.assertTrue(task.name in cron_job_names, f"Job for Task {task.name} not found in cron jobs")

        for name, job in cron_jobs.items():
            self.assertTrue(name in tasks.values_list('name', flat=True), f"Task for job {name} not found")

    def test_task_success(self):
        task = BackgroundTask.objects.get(name="isocron.TestSuccess")
        task.run_job(force=True)
        last_log = task.last_log()
        self.assertIsNotNone(last_log, "Job should have created a log entry")
        self.assertEqual(last_log.state, TaskLog.StateType.success, "Last log state should be success")

    def test_task_failure(self):
        task = BackgroundTask.objects.get(name="isocron.TestFailure")
        task.run_job(force=True)
        last_log = task.last_log()
        self.assertIsNotNone(last_log, "Job should have created a log entry")
        self.assertEqual(last_log.state, TaskLog.StateType.failed, "Last log state should be failed")

    def test_last_log_returns_latest(self):
        task = BackgroundTask.objects.get(name="isocron.TestSuccess")
        log1 = task.save_log("First", TaskLog.StateType.success)
        log2 = task.save_log("Second", TaskLog.StateType.failed)
        self.assertEqual(task.last_log(), log2)
        self.assertEqual(log1.state, TaskLog.StateType.success, "First log state should be success")
        self.assertEqual(log2.state, TaskLog.StateType.failed, "Second log state should be failed")

    def test_save_log_and_clean_logs(self):
        task = BackgroundTask.objects.get(name="isocron.TestSuccess")
        for i in range(3):
            task.save_log(f"Log {i}", TaskLog.StateType.success)
        self.assertEqual(task.logs.count(), 2)

    def test_never_ran_is_due(self):
        task = BackgroundTask.objects.get(name="isocron.TestSuccess")
        self.assertTrue(task.is_due(), "Task should be due if it has never run")


class TestNextRunTime(unittest.TestCase):
    def setUp(self):
        self.tz = timezone.get_current_timezone()
        self.fixed_now = datetime(2024, 6, 1, 10, 0, 0, tzinfo=self.tz)
        patcher = patch('django.utils.timezone.now', return_value=self.fixed_now)
        self.addCleanup(patcher.stop)
        self.mock_now = patcher.start()

    def test_no_run_every_no_run_at(self):
        self.assertIsNone(next_run_time(None, None))

    def test_run_every_time_today(self):
        result = next_run_time("T12:00", None, last_time=datetime(2024, 6, 1, 9, 0, 0, tzinfo=self.tz))
        self.assertEqual(result.hour, 12)
        self.assertEqual(result.day, 1)

    def test_run_every_time_tomorrow_if_past(self):
        result = next_run_time("T09:00", None, last_time=datetime(2024, 6, 1, 9, 0, 0, tzinfo=self.tz))
        self.assertEqual(result.hour, 9)
        self.assertEqual(result.day, 2)

    def test_run_every_duration(self):
        result = next_run_time("PT1H", None, last_time=self.fixed_now)
        self.assertEqual(result.hour, 11)
        self.assertEqual(result.day, 1)

    def test_run_every_duration_no_last_time(self):
        result = next_run_time("PT1H", None, last_time=None)
        self.assertEqual(result, self.fixed_now)

    def test_run_at_only_today(self):
        result = next_run_time(None, "T15:00", last_time=datetime(2024, 6, 1, 9, 0, 0, tzinfo=self.tz))
        self.assertEqual(result.hour, 15)
        self.assertEqual(result.day, 1)

    def test_run_at_only_tomorrow_if_past(self):
        result = next_run_time(None, "T09:00", last_time=datetime(2024, 6, 1, 9, 0, 0, tzinfo=self.tz))
        self.assertEqual(result.hour, 9)
        self.assertEqual(result.day, 2)

    def test_run_every_duration_and_run_at_long_duration(self):
        result = next_run_time("P2D", "T08:00", last_time=datetime(2024, 5, 30, 10, 0, 0, tzinfo=self.tz))
        self.assertEqual(result.hour, 8)
        self.assertEqual(result.day, 1)  # 2024-06-01 08:00
