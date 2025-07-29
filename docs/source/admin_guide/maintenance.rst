
System Maintenance
==================

.. _backup-restore:

Backup and Restore
------------------
When deployed as described in the installation guide, the USO system uses a PostgreSQL database to store all data.
It is crucial to regularly back up this database and any user data to prevent data loss. Backing up the database
for an instance using the containerized deployment is straightforward, as the database is stored in a persistent volume.

The easiest way to backup the database in this case is to create an archive of the `database` directory, which contains
the PostgreSQL data files. This can be done using the following command:

.. code-block:: bash

   tar -czf backup-$(date +"%Y-%m-%d").tar.gz ./database


Restoring the database from this backup is as simple as extracting the archive into the `database` directory of
USO instance.

.. warning::
   To avoid data corruption, it is advisable to stop the application before backing up or restoring it.


Alternatively, if using an external database, follow the instructions at
`PostgreSQL documentation <https://www.postgresql.org/docs/current/backup-dump.html>`_ to create a backup of the
database.

It is also recommended to back up the `local` directory, which contains site-specific configuration files. These
files will not be overwritten during updates, but it is good practice to keep a backup of them as well.


Updating the USO System
-----------------------
The deployment scheme described in the installation guide allows for easy updates to the USO system. To update your
instance, follow these steps:

1. **Stop the Application:**
   Before updating, it is a good practice to stop the application to prevent any data corruption or inconsistencies.
   You can do this by running:

   .. code-block:: bash

      podman-compose down

   This command will stop all running containers associated with your USO instance.

2. **Backup your current database:**
   Using the method described under the :ref:`Backup and Restore <backup-restore>` section above. For example:

   .. code-block:: bash

        tar -czf backup-$(date +"%Y-%m-%d").tar.gz ./database

3. **Pull the Latest Changes:**
   Navigate to the directory where you cloned the USO repository and pull the latest changes from the GitHub repository:

   .. code-block:: bash

      git pull origin main


4. **Rebuild the Docker Image:**
    After pulling the latest changes, you need to rebuild the Docker image to include the updates. Run the following command:

   .. code-block:: bash

       ./deploy/build-image.sh

   This script will rebuild the Docker image with the latest code changes and create images tagged with the current
   version and will also change the label of the `usonline:latest` image to point to the newly built image.

5. **Restart the Application:**
   If your `docker-compose.yml` file is set up to reference the `usonline:latest` image, you can restart the application
   using the following command:

   .. code-block:: bash

      podman-compose up -d

   This command will start the application in detached mode. All database migrations since the last release will be
   automatically applied and the application will start.
