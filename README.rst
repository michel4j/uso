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

5. Access the USO site at http://localhost:8080/


Documentation
=============
Detailed documentation is available at https://michel4j.github.io/uso/introduction/overview.html.
