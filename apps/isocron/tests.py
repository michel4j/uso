import unittest
from unittest.mock import patch
from datetime import datetime
from django.utils import timezone
from django.test import TestCase
from isocron.models import BackgroundTask, TaskLog, calculate_run_time
from isocron import autodiscover, BaseCronJob, parse_iso


class TestSuccess(BaseCronJob):
    """
    Fetch the latest biosync data from the PDB and update the local database.
    """
    run_every = "P7D"
    run_at = ["12:00", "14:30"]

    def do(self):
        return "Test success"


class TestFailure(BaseCronJob):
    """
    Fetch the latest biosync data from the PDB and update the local database.
    """
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
        self.assertEqual(task1.run_at, ["12:00", "14:30"], "Run at for TestSuccess should be ['12:00', '14:30']")
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
        task = BackgroundTask.objects.create(name="TestTask4")
        log1 = task.save_log("First", TaskLog.StateType.success)
        log2 = task.save_log("Second", TaskLog.StateType.failed)
        self.assertEqual(task.last_log(), log2)
        self.assertEqual(log1.state, TaskLog.StateType.success, "First log state should be success")
        self.assertEqual(log2.state, TaskLog.StateType.failed, "Second log state should be failed")


class CalculateRunTimesTests(unittest.TestCase):
    def test_calculate_run_times_today(self):
        now = timezone.now()
        run_time = calculate_run_time("23:59", dt=now)

        self.assertTrue(isinstance(run_time, datetime))
        self.assertEqual(run_time.year, now.year)
        self.assertEqual(run_time.month, now.month)
        self.assertEqual(run_time.day, now.day if run_time > now else now.day + 1)

    def test_calculate_run_times_rollover(self):
        # If time is before now, should roll over to next day
        now = timezone.now().replace(hour=23, minute=59)
        run_time = calculate_run_time("00:01", dt=now)
        expected_day = now.day + 1 if now.hour > 0 else now.day
        self.assertEqual(run_time.day, expected_day)

    def test_calculate_run_times_invalid(self):
        now = timezone.now()
        run_time = calculate_run_time("not-a-time", dt=now)
        self.assertEqual(run_time, None)

"""
    def test_tasklog_creation_and_relation(self):
        task = BackgroundTask.objects.create(name="TestTask2")
        log = TaskLog.objects.create(task=task, message="Started", state=TaskLog.StateType.running)
        self.assertEqual(log.task, task)
        self.assertEqual(task.logs.count(), 1)
        self.assertEqual(log.state, TaskLog.StateType.running)

    def test_save_log_and_clean_logs(self):
        task = BackgroundTask.objects.create(name="TestTask3", keep_logs=2)
        for i in range(3):
            task.save_log(f"Log {i}", TaskLog.StateType.success)
        self.assertEqual(task.logs.count(), 2)

    def test_last_log_returns_latest(self):
        task = BackgroundTask.objects.create(name="TestTask4")
        log1 = task.save_log("First", TaskLog.StateType.success)
        log2 = task.save_log("Second", TaskLog.StateType.failed)
        self.assertEqual(task.last_log(), log2)

    def test_next_run_time_no_logs_returns_now(self):
        task = BackgroundTask.objects.create(name="TestTask5")
        now = timezone.now()
        next_run = task.next_run_time()
        self.assertTrue(abs((next_run - now).total_seconds()) < 2)

    @patch('isocron.models.BackgroundTask.next_run_time')
    def test_is_due_true_when_next_run_time_now(self, mock_next_run_time):
        task = BackgroundTask.objects.create(name="TestTask6")
        mock_next_run_time.return_value = timezone.now()
        self.assertTrue(task.is_due())

"""