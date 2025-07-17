User Services Online
********************

Introduction
============

Background
----------
The User Services Online (USO) is an information management system developed at
the Canadian Light Source which manages all information related to the use of a
synchrotron facility.

Scope
-----
The system provides the following feature sets:

    * Registration of new users
    * Proposal creation and management: composition, submission, clarification
    * Publications: submission, tracking and metrics reporting
    * Beamline/Facility Management: configuration of available techniques
    * Reviewer profiles: subject areas, techniques, automated reviewer assignment
    * Reviews: Scientific, Technical, Safety, Ethics, Equipment
    * Allocation of shifts: allocation pools, automatic decision bands
    * Project management: materials, amendments
    * Scheduling: facility modes, beam time, user support
    * Electronic Permits: beamline sessions, lab sessions, permission verification at sign-on
    * User Feedback collection and reporting
    * User/Institutional agreements
    * Generation of Statistics, Metrics and Reporting


Deploying an instance
=====================

1. From the top-level directory, run the command `prepare-instance.sh` as follows:

   .. code-block:: bash

      ./deploy/prepare-instance.sh <deploy top-level directory>

2. This command will build a docker/podman image "usonline:latest" and create a barebones directory structure. Add any
   data you want to load into the "local/kickstart/" in either YAML or JSON format. The data should be in the format
   similar to that produced by the Django "dumpdata" command.
3. Edit the docker-compose.yml file to reflect your deployment environment. Change the environment settings to create
   the appropriate database and uso admin accounts.
4. Run the docker-compose up command to start the database and USO. The database will be initialized with the data in
   the kickstart directory if provided.

   .. code-block:: bash

       docker-compose up -d

   OR

   .. code-block:: bash

       podman-compose up -d

5. Access the USO site at http://localhost:8080/. The default admin account is "admin" with password "usoadmin" unless you
   changed the value in "docker-compose.yml".
6. Logos are needed in a few places. To customize the logo, place two PNG files in the "local/media/logos" directory
   named "logo-horiz.png" (300 x 90, logo) and "logo-oriz-white.png" (White version for dark backgrounds).
7. By default, Profile photos for users should be placed in the "local/media/idphoto/<username>.jpg" for each user.
   Alternatively, they can be fetched from a remote server through the Profile manager. See RemoteProfileManager for an
   example. The photo should be minimum 200 x 200 pixels.

The system is now ready for use.


Main Concepts
=============
Users
    Anyone who uses the USO system needs a user-account in order
    to use the system. Accounts can be requested through a registration which
    is completed through the USO system for non-users. On successful registration,
    and verification of the user's email address, an account is created. It is highly
    recommended to use institutional email addresses for registration.

Role
    A prescribed function or status conferred on a person. An individual's roles will
    determine which USO pages they can view, which tasks they may be expected to complete. Roles
    can be managed externally to the USO software and provided through an API. Roles in the USO system are often
    labelled using hyphenated lowercased words joined by colons. The words after the colon identify the realms. Roles
    used by the system can be configured in the local settings file using the following settings parameters.

    For example:

    .. code-block:: python

        USO_ADMIN_ROLES = ["admin:uso"]                     # Admins of the USO system
        USO_CONTRACTS_ROLES = ["staff:contracts"]           # Contracts staff
        USO_CURATOR_ROLES = ["curator:publications"]        # Publications Curator
        USO_HSE_ROLES = ["staff:hse"]                       # Health and Safety staff, who perform safety reviews
        USO_MANAGER_ROLES = ["manager:science"]             # Science Manager
        USO_REVIEWER_ROLES = ["reviewer"]                   # Scientific Reviewers
        USO_STAFF_ROLES = ["staff"]                         # General Staff, note that "staff:uso" implies "staff"
        USO_STUDENT_ROLES = ["student"]                     # Students
        USO_USER_ROLES = ["user"]                           # Other non-staff users
        USO_FACILITY_ADMIN_ROLE = 'admin:-'                 # role templates '-' means propagate down subunits
        USO_FACILITY_STAFF_ROLE = 'staff:-'                 # '+' means propagate up subunits

    Facility roles are special roles which are used to manage access to facilities. The roles can be specified
    be specified with wildcards to allow for propagation of roles to subunits. For example, the role "admin:-"
    will propagate the role "admin" to all subunits of the facility. The role "staff:+" will propagate the role
    to all parent units of the facility. The role "staff:*" is equivalent to "staff:{}" and will not propagate beyond
    the current facility. For example if a user has the role "staff:cmcf" and the facility has a parent facility "bio"
    and a sub-facility "cmcf-bm", setting USO_FACILITY_STAFF_ROLE to "staff:-" implies that users with "staff:bio"
    roles will implicitly have "staff:cmcf" roles and users with "staff:cmcf" roles will implicitly have "staff:cmcf-bm".
    However "staff:cmcf" will not necessarily have "staff:bio" roles.


Permission
    A qualification that permits a person to carry out a task. Usually acquired after appropriate
    training has been completed. Permissions can be stored and managed externally to the USO software.
    Permissions are often labelled using hyphenated uppercased words in the USO system.

    Some Examples of permissions:

    - *FACILITY-ACCESS*: Equivalent to a valid access badge to enter the facility.
    - *CRYO-WORKER*:  Qualified to work with cryogenics
    - *CMCF-ID-USER*: Qualified to perform experiments on the CMCF-ID beamline. Every beamline
      has a unique permissions for access which is of the form "<beamline.acronym>-USER",
      "<beamline.acronym>-REMOTE-USER".
    - *LAB-ACCESS*: Qualified to work in a laboratory
    - *ANIMAL-WORKER*: Qualified to work with animals.

Proposal
    A document submitted by prospective users which describes the planned research
    to be performed, the samples and other materials which will be brought or used for the experiments
    and the facilities being requested for the experiments.

Cycle
    A period of time, typically 6 months long, during which experiments are scheduled and performed
    at the facility. There are typically two cycles per year Jan 1st - June 30, and July 1st - Dec 31st.

Facility Configuration
    This is the specification of all the techniques available on the given beamline starting from
    specified cycle, and the review track through which submissions will be reviewed. Configurations for a
    given cycle can be edited until the day before the call opens. Only individuals
    with Beamline Administrator Roles can edit or create configurations.

Schedule
    Each Cycle is associated with a schedule on which events can be scheduled. The period of the schedule
    corresponds to the start and end dates of the Cycle. Events can only be scheduled for this period.

    Examples of types of events include:

    - *Facility Modes*: These define the overall state of the facility for each shift
      and is the source of information used in determining the number of shifts
      available for allocation.
    - *Beam Time*:  Scheduled beam time for projects. Beamlines can decide to
      schedule shifts in 4HR, or 8HR blocks.
    - *Support Staff*:  Beamline user-support can be scheduled. Only staff who are
      recognized as having the role of *Beamline Staff* on a given beamline, can
      be scheduled for user support.

Call for Proposals
    The period during which proposals are accepted for a given Cycle. This period is usually
    4 weeks long and occurs about 4 months before the start date of the given Cycle.

Review Track
    A prescribed sequence of reviews through which submitted proposals (Submissions) are subjected. Submissions
    undergo reviews based on the types of proposals the requested facilities, and when they were submitted.
    Some proposals may result in multiple submissions if the requested facilities were configured to require
    more than one Review Track. There is no limit to the number of ReviewTracks that can be created.

    Examples of Review Tracks:

    - *General User (GU)*: This is the typical method of review of submissions,
      involving both technical review by beamline staff, and scientific review by
      external peers. Scientific review is overseen by a Peer-Review committee of
      international experts.
    - *Macromolecular Crystallography (MX)*: Similar to the GU track but
      the Peer-Review committee is separate
    - *Rapid Access (RA)*: A special review track for submissions received after the
      Call for Proposals has closed, for commissioning, emergency requests, or
      priority access. Restrictions may apply to submissions received through this
      method.

ReviewType and FormType
    The type of review to be completed. The review type species the review FormType, the scoring scheme in the form of
    score fields and weighting for the specific FormType, and the reviewer role required to complete the review. The FormType
    is a dynamic form specification which includes all the questions to be answered during the review process. FormTypes
    and ReviewTypes can be managed through the USO system administrator screens. Configuration of which ReviewTypes
    are used for creating scientific, technical and safety reviews is accomplished through the following configuration
    parameters.

    An example scoring scheme where scores are calculated as a weighted average of three different fields, would be
    implemented as "{'field_one': 0.6, 'field_two': 0.2, 'field_three': 0.2}". Within the form designer, each of the
    fields may represent a number of possible values and are by default always a non-zero integer value. The final score
    is calculated as a sum of all the field values multiplied by the corresponding weight. The final score can then have
    a wide variety of possible values, depending on the number of fields, the number of choices per field, and the range
    of values for the weights. Even the ordering of values can be different so that either low or high values are considered
    better.

Review
    A questionnaire to be completed online. The questionnaire varies depending
    on the ReviewType to be completed. Reviews are usually
    assigned to a person (Reviewer) or to a Role. When assigned to a role, any individual who has the role
    can claim and complete the review. In addition, any individual who has the role can re-claim
    and complete a partially completed review started by someone else. However, when assigned
    to a person, only the assigned person is allowed to complete the review. All reviews must be
    be completed online through the USO system.

Clarification
    A question asked by a reviewer to the spokesperson (or delegate, or project leader) during the review
    process. Clarification responses can be provided by either the spokesperson, delegate or leader.

Project
    The project, is the central hub through which users use the facility. A project will be
    created only if the submission is successful after review. Only one project can result from a
    given proposal, even if the proposal resulted in multiple submissions. Most projects originating
    from submissions which went through the GU/MX tracks will be active for 2 years. Non-priority access
    requests which went through the RA track are only valid until the end of the requested cycle.
    Some special classes of projects may have unlimited validity.

Allocation
    A decision which allows a project to perform experiments on a specific beamline. Most beamlines
    allocate beam time in advance of the cycle. For these beamlines, the allocation is the number
    of shifts of beam time reserved for the project on the given beamline during the cycle. An
    allocation of zero shifts means no beam time was reserved, even though the project may have been
    successfully reviewed. Allocations are assigned on a per-cycle basis. All active projects wishing
    to be allocated beamtime during any cycle occurring within their period of validity, must renew
    their allocations when the *Call for Proposals* is open for that cycle. This is the case even
    for projects which got zero shifts during the previous cycle. On beamlines (and other facilities)
    which do not allocate beam time in advance, allocations are not assigned, and those projects will require
    renewal each cycle. Instead, beam time can be requested as needed throughout the period of validity.

Research Team
    All the individuals associated with the project and allowed to participate on the planned experiments.
    The spokesperson is the individual who authored the proposal, the project leader is the Principal Investigator,
    and the delegate is another individual who may carry out tasks related to the project and respond to clarifications
    on behalf of the spokesperson. Each person on the team, except for the spokesperson can voluntarily remove themselves
    from the team but only the spokesperson, the delegate, or the project leader (if specified) can add a person
    to the team. Team members and changes to the team are not reviewed but only members who meet all
    required qualifications will be able to participate.

Materials
    The collection of information about the samples, equipment, ancillaries, and safety procedures
    related to the project, which the research team is planning to bring or use at the facility.
    Materials require safety review and approval before any experiments using them can proceed. Based on
    the nature of the experiments and the declared materials, additional information may be required for the
    safety review, in addition to the information submitted with the original proposal. When applicable
    such information will be clearly displayed as warnings on the project. Safety review may result in
    approval of all the materials, only some of them, or rejection. Changes to materials can be initiated
    through amendments which can be submitted at any time and will require review and approval before use.
    Note that each user can manage a list of pre-defined samples which can be re-used in multiple proposals
    and materials. Reviews of materials containing previously reviewed samples may be expedited.

Session
    A period of time during which a project is using a beamline/facility. A valid session requires
    a few steps to establish:

    - *Hand-Over*: An action performed by beamline staff to hand over a beamline to a specific project
      for a specific time slot. A hand-over is required before user experiments can start.
    - *Sign-On*: An action performed by the spokesperson to assume responsibility for the beamline during
      the period prescribed period. The sign-on is only possible after a hand-over. During the sign-on,
      the spokesperson must select all participating team members and samples they plan to use during that session.
      Only approved samples may be selected. In addition, the qualifications of each team member will be verified.
      Participating team members and samples can be added at any time during the session, and beamline staff
      can extend the duration of the session at any time during the session.
    - *Sign-Off*: An action performed by a team member to indicate completion of the session and confirm that
      samples have been removed from the facility. If no sign-off is performed, it will be performed automatically
      by the system and the beamline staff will be notified.

    NOTE: A successful sign-on results in a valid electronic permit to use the beamline which will remain valid
    until signed-off or terminated. Sessions can be terminated at any time by Health & Safety staff.

Lab Session
    Similar to a beamline session, except a hand-over is not needed, and it is not required to declare the samples in use.
    A valid project is required in order to complete a Lab Sign-on and a valid Lab Session is required in order to use
    a lab. During the sign-on process, the user selects the desired Lab, workstations, ancillary equipment, team members
    and planned time slot.

    NOTE: A successful lab sign-on results in a valid electronic permit to use the lab.


Cycle States
------------
Cycles automatically switch states on the prescribed dates. On the *open date*, the state
switches automatically to **"Call Open"** and will remain in that state until the *close date*,
at the end of which the cycle state switches to **"Assigning"**. During this state, Scientific reviews
should be assigned. Reviews can be assigned either manually or using the automatic assignment
triggered by administrators. After the assignments have been verified and are satisfactory,
the review process can be started using a manual trigger on the Cycle detail page. This
process sends notification emails to reviewers and switches the cycle state to **"Review"**.

On the *close date* all reviews are automatically closed but the cycle state remains in **"Review"**
until the *allocation date*. It is expected that the time between the *close date* and the
*allocation date* will be used for Peer-Review Committee meetings, score adjustments and updating
of comments for applicants. Early on the *allocation date*, the system creates projects according
to the submissions and their review results and prepares for allocation. The state of the Cycle is also
changed to **"Evaluation"**. Allocations can not be done prior to this day but must be completed on
the *allocation date*. Just after midnight on the allocation date, notification emails are sent to
users informing them of their review results and allocations. The cycle state is then switched
to **"Scheduling"** and will stay in that state until the cycle starts.

On the *start date*, the state becomes **"Active"** and on the *end date* it switches to **"Archived"**.

User/Institutional Agreements
-----------------------------
The system implements *User Agreements*.  Agreements created in the system and required of users prior to
experiments.  *Institutional Agreements* can also required of users' institutions.

The *User* role is not assigned at registration. Instead, Any person submitting a
proposal or participating on a research team will automatically be assigned the *User* role.

Every person with the *User* role will be required to accept any *User Agreements* assigned to the *User* role. However,
their institution must have a valid *Institutional Agreement* in place before they can accept the
*User agreement*. If the process to establish the *Institutional Agreement* has not been initiated,
users will be presented with a form requesting the contact person at their institution for that purpose. Individual
institutions can be exempted from the requirement to have an *Institutional Agreement* in place.

User-Interface Components:
==========================

The USO user interfaces are built from similar components and interaction relies on the same concepts
throughout.

Icon Tool
    An icon with a descriptive text underneath. Single-clicking on the tool initiates
    an action such as opening a form or a pop-up, or redirecting to another page. On
    small screens, or when more space is needed on the screen, only the icon is shown.

Side-Bar Menu
    The dark vertical area to the left of the window with multiple icon tools. Clicking
    on the items in the menu expands the menu to show a sub-menu. The specific
    items visible on your menu will depend on your roles.

Page Header
    The region at the top of the browser window is the page header. Usually the main title of the page
    is displayed here and gives some guidance about the context of the current page. Breadcrumbs are
    usually displayed underneath the title and provide relative navigation links relevant to the page.

Notification Area
    To the right of the header region is the notification bell which may sometimes show the number
    of unread notifications. Single-clicking on the bell reveals the list of recent notifications.

Profile Menu
    The profile menu contains links for performing actions related to the account of the currently logged-in user.
    The profile menu can be activated by clicking on the photograph at the far right of the header region.

Dashboard
    The dashboard is the landing page of the user and contains a number of cards which summarize various
    pieces of information relevant to the current moment in time. Most of the information presented on the dashboard
    can be accessed in more detail through other pages in the USO system. The specific cards visible will depend on the
    user's roles. Each card has a descriptive header and may contain relevant icon tools at the top-right
    corner of the card header.

    .. figure:: docs/source/dashboard.png
        :width: 800px
        :align: center
        :alt: Dashboard

        Screenshot of the dashboard showing the Side-bar menu with icon tools, and various dashboard cards.

List Page
    A list page, is a page which presents a table objects (eg, lists of samples, proposals, projects, etc).
    List pages enables users to view all entries in table format, search through them, sort and order them
    based on different fields (or columns) and filter them based on status, or other properties such as
    modification date. It may sometimes be possible to add new entries from the list page. In some cases,
    single-clicking on a row of the table redirects access to the detailed page for the selected item, or
    presents a form to allow editing the details of the selected item. All list pages follow the same
    paradigms and often contain a search box, list filters, item counts, list tools, a list header, and
    pagination tools.

    .. figure:: docs/source/proposals-list.png
        :width: 800px
        :align: center
        :alt: List Page

        Screenshot of the proposals List Page.

Detail Page
    A detail page is a page which presents information about a specific item in the system (eg. Proposal,
    Submission, Project, Session, Beamline etc). Detail pages also follow the same paradigms and often contain
    a header region, a tool area, a status area and a content area. The content area may vary significantly from
    one object type to another and may also vary based on the state of the object. The status area may
    have a colored background which provide visual cues about the state of the object.

    .. figure:: docs/source/beamline-detail.png
        :width: 800px
        :align: center
        :alt: Beamline Detail Page

        Screenshot of a Beamline Detail Page.

    .. figure:: docs/source/project-detail.png
        :width: 800px
        :align: center
        :alt: Project Detail Page

        Screenshot of a Project Detail Page.