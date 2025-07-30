Setting up a Development Environment
====================================

To get started developing or contributing to the USO system, you will need to set up a local development environment.
The only external software required is Git, Python and Docker or Podman. We recommend Python 3.13 although all versions from
Python 3.10 to 3.13 are currently supported.

If you plan to make contributions to the USO system, we recommend that you "fork" the repository on GitHub and
clone your forked repository to your local machine. This allows you to work on your own copy of the codebase and submit
pull requests with your changes if you want to contribute back to the main project.

Follow these steps to set up your development environment:

1. Use Git to clone the USO repository from GitHub:

   .. code-block:: bash

      git clone https://github.com/<my-forked-project>/uso


2. Setup a Python virtual environment to isolate your development environment from the system Python packages. Based
   on your Python IDE, this can be done in different ways. For example, using the `venv` module, you can create a
   virtual environment by running:

   .. code-block:: bash

       python3 -m venv .venv

   Activate the virtual environment:

   .. code-block:: bash

       source .venv/bin/activate

3. **Install Dependencies:**
   Install the dependencies within your active virtual environment:

   .. code-block:: bash

      pip install -r requirements.txt

4. Prepare the Cache and Database containers. The USO system uses a PostgreSQL database and a Memcached cache.
   You can use the provided `docker-compose.yml` file to
   set up these containers. Create a `local` directory inside the top-level of the uso repository.  This directory
   is ignored in `.gitignore` so it won't be included in the repository. You can create the required directories
   and configuration files by running the following command:

   .. code-block:: bash

       ./deploy/prepare-dev.sh


   Edit and configuration files to update the database connection settings and other parameters as needed. Note
   that the this command will bind the database and cache containers to the host ports 5432 and 11211 respectively, so
   make sure these ports are not in use by other applications on your system. Then start the containers using:

   .. code-block:: bash

       podman-compose up -d

5. The `local/settings.py` file contains the configuration for your local development environment. You will need to
   update the database connection settings, and cache settings, as follows.

   Change the HOST entry under the `DATABASES` section to point to the PostgreSQL container and port:

   .. code-block:: python

        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                ...
                'HOST': 'localhost',        # use localhost instead of 'database'
                'PORT': '5432',
            }
        }

   For the cache settings, you can use the following configuration to connect to the Memcached container:

   .. code-block:: python

        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
                'LOCATION': 'localhost:11211',    # use localhost instead of 'cache'
            }
        }


6. Run Database Migrations: After setting up the database connection, you need to apply the initial database migrations.
   Run the following command from the top-level directory of the USO repository from within your virtual environment:

   .. code-block:: bash

      ./manage.py migrate

7. Create a Superuser Account: To access the admin interface and manage the USO system, you need to create a super
   user account. Run the following command and follow the prompts to create a superuser:

   .. code-block:: bash

       ./manage.py createsuperuser

8. Load data fixtures: This step is required to load initial data required by the system.  Use the `loaddata` command
   as follows:

   .. code-block:: bash

      ./manage.py loaddata initial-data

9. Load additional data [optional]: If you want to generate and load fake data for testing purposes, you can use the
   `generate-data.py` script provided in the `deploy` directory. This script allows you to generate random data for users,
   proposals, and other entities in the USO system.

   .. code-block:: bash

       ./deploy/generate-data.py -u 1000 -p 200 ./local

   This command will generate 1000 users and 200 proposals with random data. within the `local/kickstart` directory.
   You can load this data into the database using the `loaddata` commands:

   .. code-block:: bash

        ./manage.py loaddata ./local/kickstart/000-facilities.yml
        ./manage.py loaddata ./local/kickstart/001-users.yml
        ./manage.py loaddata ./local/kickstart/002-samples.yml
        ./manage.py loaddata ./local/kickstart/003-proposals.yml

10. Finally, you can start the development server to test your setup. Run the following command:

   .. code-block:: bash

        ./manage.py runserver

   This will start the development server on `http://localhost:8000/`. You can access the USO system in your web
   browser by navigating to this URL and log in using the superuser account you created earlier.

.. note::

    If you plan to make changes to the frontend code, make sure you have configured your development IDE to
    automatically compile SCSS files to CSS files and minify JavaScript files. This will ensure that your changes are
    reflected in the development server without needing to manually compile the files each time.