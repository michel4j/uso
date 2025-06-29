import unittest
from unittest.mock import patch
from datetime import datetime
from django.utils import timezone
from django.test import TestCase
from isocron.models import BackgroundTask, TaskLog
from isocron import autodiscover, BaseCronJob, parse_iso


class TestSuccess(BaseCronJob):
    """
    Fetch the latest biosync data from the PDB and update the local database.
    """
    run_every = "P7D"
    run_at = "12:00"
    keep_logs = 2

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
