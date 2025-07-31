
.. _background-tasks:

Background Tasks
================
The USO system relies on background tasks to manage the lifecycle of cycles, proposals, submissions, reviews, and projects.
These tasks are responsible for automatically updating the state of cycles, proposals, and submissions based on
the defined rules and schedules. Background tasks are scheduled to run periodically, ensuring that the system remains
up-to-date and that the lifecycle of cycles, proposals, and submissions is managed efficiently.

Background tasks are managed by User Office Administrators through the
:menuselection:`Admin --> Background Tasks` section of the USO system menu. This section provides an overview of the
background tasks that are currently available, their status, run frequency, the last time they ran, the log messages
from the last run, and the next scheduled run.

.. figure:: background-tasks.png
    :alt: Background Tasks
    :align: center

    A screenshot of the Background Tasks page showing the list of available tasks and their status.

To view the details of a specific background task, click on the task name. This will display the task details,
including the task description, the last run time, and the next scheduled run time. You can also view the log messages
from the last run, which can help you diagnose any issues that may have occurred during the task execution.

.. figure:: background-task-details.png
    :alt: Background Task Details
    :align: center

    A screenshot of the Background Task details page showing the task description, last run time, next scheduled run time,
    and log messages from the last run.

To run a background task manually, click the :guilabel:`Run Now` button on the task details page.

.. note::
    Running a background task manually will execute the task immediately, regardless of its scheduled run time. This can
    be useful for testing or debugging purposes, but should be used with caution in production environments. Also,
    for tasks that run based on an interval, running them manually will change the next scheduled run time, since
    run times are calculated based on the last run time.


The following background tasks are available in the USO system:

- **AdvanceReviewWorkflow**: This task advances the review workflow for proposals and submissions
  based on the defined rules. It runs every 15 minutes.
- **CreateCycles**: This task creates new cycles based on the defined Cycle Types. It runs once a day and ensures
  new cycles exist for each active Cycle Type for the next 2 years.
- **CycleStateManager**: This task manages the state transitions of cycles. It runs every hour.
- **RemindReviewers**: This task sends reminders to reviewers about pending reviews that are due soon. It runs
  at 02:00 AM every day.
- **StartReviews**: This task starts the review process for proposals and submissions that are ready for review. While
  the **AdvanceReviewWorkflow** task creates new reviews, they stay in the pending state until this task runs. It opens
  pending reviews and notifies reviewers about their assigned reviews. It runs every 6 hours. To minimize the number
  of emails sent to reviewers. Notifications of multiple reviews to a single reviewer are combined into a single
  email message.
- **AutoSignOff**: This task automatically signs off project sessions automatically if users have not signed-off after
  their session ends. It runs every 4 hours.
- **CreateCallProjects**: This task creates projects for submissions to Review Tracks that require a call. This
  task only runs at 00:15 AM on the allocation date of the cycle.
- **CreateNonCallProjects**: This task creates projects for submissions to Review Tracks that do not require a call.
  It runs every 15 minutes.
- **NotifyProjects**: This task sends notifications to users about the result of their submissions and projects,
  after reviews are completed and allocations have been performed. It runs at 00:30 AM on the day after
  the allocation date.
- **FetchBioSync**: This task fetches PDB deposits data from the BioSync Database. Since various PDB APIs have
  changed recently, this task will soon be replaced. It runs once a week.
- **UpdateMetrics**: This task fetches fetches Journal Metrics from SciMajor and updates the metrics for
  publications in the USO system. It runs once a quarter (every 3 months).
- **FetchCitations**: Fetches citation data from the CrossRef database and updates the
  publication records in the USO system. It runs once a month.
- **UpdatePublications**: Update the meta-data for all articles published in the current month. Runs once a week.
- **CleanRegistrations**: This task cleans up old user registrations that have not been activated. It runs once a day.
- **NotifyNewInstitutions**: This task sends notifications to administrators about new institutions that have been
  created and pending approval. It runs once a day.
- **SyncUsers**: This task synchronizes user data with the external user management system (if configured).
  It runs once an hour.