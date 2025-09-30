# Changelog v25.09

## New Features
*   **Reporting:**
    *   Added new report entries and updated existing report configurations.
    *   Added subquery aggregation expressions for Min, Max, Count, Avg, and Sum.
    *   Enhanced reporting capabilities with new data sources and refined entries.
    *   Added a new "Reports" menu and views for handling journal metrics.
    *   Added a report builder.
*   **User and Access Management:**
    *   Added image upload functionality to the user profile.
    *   Introduced "Access Pools" for proposal submissions, allowing for better organization and filtering of tracks.
    *   Added the ability to define an optional scientific reviewer pool for each track.
    *   Implemented management features for "Techniques" and "Review Types".
    *   Added safety management features for hazardous substances and permissions.
*   **Surveys and Feedback:**
    *   Added new data fields for feedback surveys, including a randomizer for Likert scale responses.
    *   Introduced "Category" and "Rating" models to enhance feedback structure and aggregation.
*   **Proposals and Reviews:**
    *   Added "SubjectArea" and "FocusArea" management.
    *   The review process now supports automatic creation and starting of review stages.
    *   Added a review summary display for closed reviews.
    *   Added `auto_create` and `max_workload` fields to the `ReviewStage` model.

## Improvements
*   **UI/UX:**
    *   Updated and improved various UI elements, including forms, buttons, and navigation.
    *   Refactored many templates for Bootstrap 5 compatibility, improving layout and styling.
    *   Improved the display of survey details.
    *   Enhanced the layout and styling of the calendar, word cloud, and various other components.
    *   Added a custom 50x error page and updated error message formatting.
    *   The user interface for reviewer assignment has been enhanced.
    *   Improved the layout and accessibility of many forms and templates.
*   **Performance and Refactoring:**
    *   Refactored settings to use environment variables for server configuration.
    *   The Docker setup has been refactored to support separate deployment configurations for Apache and Nginx.
    *   Many parts of the codebase have been refactored for better organization, clarity, and maintainability.
    *   Replaced `StringListField` with `JSONField` for roles and admin_roles in `Agreement` and `Ancillary` models.
    *   The proposal model now uses a `JSONField` for the team.
*   **Data Generation:**
    *   The data generation script has been enhanced with more realistic data and better handling of various scenarios.
*   **Dependencies:**
    *   Updated Python to version 3.13 and updated several Django-related dependencies.

## Bug Fixes
*   Fixed a bug in the proposal preview when displayed outside of the review context.
*   Fixed an issue with cloning submitted proposals.
*   Fixed a bug in the data generation and deployment scripts related to password setting.
*   Fixed an issue with the `isnull` check.
*   Fixed a bug in the review advancement date check.
*   Fixed the isocron log display to show tasks in alphabetical order.
*   Fixed breadcrumb links and allocation project counts.
*   Fixed an issue with standard deviation aggregation in review scores.
*   Fixed a bug in the end date calculation in the date range function.
*   Fixed a bug in the sidebar menu request handling.
*   Fixed a bug in the report print template.
*   Fixed a registration bug introduced by country/region changes.
*   Fixed an issue with cycle schedules and improved cycle creation logic in the cron job.
*   Fixed several other minor bugs and issues.

## Documentation
*   Updated and improved the deployment documentation.
*   Added documentation for the scheduling and background tasks system.
*   Added a GitHub Actions workflow for building and deploying the Sphinx documentation.
*   Expanded the user guide with more information on experiments, user registration, and interface components.
