.. _admin-configuration:

=============
Configuration
=============

The configuration parameters for a USO instance is stored in the `settings.py` file located in the `local` directory of
your USO instance.

.. note::
   The `settings.py` file in the `local` directory is not the same as the main `settings.py` file for the USO software.
   You should never change settings directly within the main USO software `settings.py` if you are just preparing
   an instance of the software. Only modify the main `settings.py` if you are making modifications of the USO software.
   All settings defined within the main `settings.py` file can be overridden by making changes to `local/settings.py`.
   You can edit this file to customize your USO instance configuration.

The default generated `local/settings.py` file contains all the relevant settings, including database configuration,
required for the USO instance to run. You can modify these settings to suit your needs, such as changing the database
connection details, configuring email settings, and setting up custom user profile managers and much more.

A few sensitive settings are stored in the `.env` file, and referenced through environment variables within
`local/settings.py`. To change these settings, you should edit the `.env` file directly instead.

The `.env` File
---------------
Here are some of the key settings you might want to configure in your `.env` file:

- **SECRET_KEY**: A unique secret key for your USO instance. This is used for cryptographic signing.
- **DATABASE_PASSWORD**: The password for the PostgreSQL database user.
- **EMAIL_PASSWORD**: The password for the email account used to send notifications.
- **OPEN_WEATHER_API_KEY**: The API key for the OpenWeather service (v2.5), used for weather
  information on the dashboard.
- **GOOGLE_API_KEY**: The Google API key used by the publications application for fetching book and patent information.

The `local/settings.py` File
----------------------------
Other settings can be configured in the `local/settings.py` file, such as:

DEBUG
.....
Set to `True` for development, `False` for production.

ALLOWED_HOSTS
.............
A list of allowed host/domain names allowed to access the USO. Use ['*'] to allow all hosts.

SITE_URL
........
The base URL of the USO instance. This is used for generating absolute URLs in emails and links. For example::

    SITE_URL = 'https://user-office.example.com'

USO_WEATHER_LOCATION
....................
The latitude and longitude of the location for which to fetch weather information as a list or tuple. For example::

    USO_WEATHER_LOCATION = (51.5074, -0.1278)  # London, UK


CACHES
......
Configuration for caching. By default, a memcache container is deployed along side the USO application and the
settings in `local/settings.py` reflect this default configuration.  However, to use a different cache backend,
or even an external server for cacheing, you can modify this dictionary.
See the `Django Documentation <https://docs.djangoproject.com/en/5.2/topics/cache/>`__ for more details.

The default configuration is as follows:

.. code-block:: python

    CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
           'LOCATION': 'cache:11211',
       }
    }

DATABASES
.........
Configuration for the PostgreSQL database. The default configuration uses a local database container
deployed along side the USO application. However, you can modify this dictionary to use an external database server
or a different database backend. Although Django supports multiple database backends, the USO system is
designed to work with PostgreSQL and some specialized database functions may not be available on another backend.
See the `Django Documentation <https://docs.djangoproject.com/en/5.2/topics/databases/>`__ for more details.

The default configuration is as follows:

.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'usonline',
            'USER': 'usonline',
            'PASSWORD': os.getenv('DATABASE_PASSWORD'),
            'HOST': 'database',
            'PORT': '',
        }
    }

.. note::
   The name of the database and the user are both set to `usonline` by default. These can be changed if you are
   using an external database server, but is not recommended to change them if you are using the default local database
   container. The database will be created automatically when the USO application starts for the first time, and
   the user will be granted the required privileges on the database.


Email Configuration
...................
To configure email settings for sending notifications, you can set the following parameters in `local/settings.py`:

- **EMAIL_BACKEND**: The email backend to use. The default is `django.core.mail.backends.smtp.EmailBackend`.
- **EMAIL_HOST**: The SMTP server to use for sending emails.
- **EMAIL_PORT**: The port to use for the SMTP server. The default is 587 for TLS.
- **EMAIL_HOST_USER**: The email address to use for sending emails.
- **EMAIL_HOST_PASSWORD**: The password for the email account used to send notifications. Set this in the `.env` file.
- **EMAIL_USE_TLS**: Whether to use TLS for the SMTP connection. Set to `True` for secure connections.
- **DEFAULT_FROM_EMAIL**: The default email address to use for sending emails. This is usually the same as `EMAIL_HOST_USER`.
- **SERVER_EMAIL**: The email address to use for server-related emails, such as error notifications.

In addition, you can set the following parameters to configure users who will receive notifications about system events:

- **ADMINS**: A list of tuples containing the names and email addresses of administrators who will receive error
  notifications.

.. note::
   When **DEBUG** is set to `True`, no external emails will be sent, all notifications generated by the USO software
   will be sent only to ADMINS. This is useful during development and testing to avoid sending test emails to real
   addresses.

Configuring Roles
-----------------
To configure roles in the USO system, you can set the following parameters in `local/settings.py`:

USO_USER_ROLES
..............
A list of strings containing the role names for users of the USO system. These users will have access to the
basic features and pages of the USO system, such as submitting proposals, managing their projects, and viewing
their sessions. The default setting is::

    USO_USER_ROLES = ['user']

USO_ADMIN_ROLES
...............
A list of strings containing the role names for users considered administrators of the USO system. These users will have
full access to all features and pages of the USO system, including administrative functions such as managing
background tasks, user accounts, and system settings. The default setting is::

    USO_ADMIN_ROLES = ['admin:uso']


USO_STAFF_ROLES
...............
A list of strings containing the role names for users considered staff members of the USO system. These users will have
access to additional features and pages beyond normal users of the USO system, but will not have access to
administrative functions. The default setting is::

    USO_STAFF_ROLES = ['staff']

USO_FACILITY_STAFF_ROLES
........................
A string containing the wildcard role template for users considered staff members of a particular facility within
USO system. These users will have access to some additional features and pages related to the facility.

Wildcard roles are used to define roles that can be applied to multiple facilities within a hierarchy. Wildcard
roles support specifying the `Realm` as a special character. For example, any of the following ::

    USO_FACILITY_STAFF_ROLES = 'staff:*'
    USO_FACILITY_STAFF_ROLES = 'staff:{}'
    USO_FACILITY_STAFF_ROLES = 'staff:-'
    USO_FACILITY_STAFF_ROLES = 'staff:+'

The meaning of the wildcard is as follows:

- `*` or `{}` matches a specific facility only. Within the context of a specific facility, the `*` is replaced with the acronym
  of the target facility before checking of the user has the role. For example, if the facility acronym is `MX-ID`,
  then a user with the role `staff:mx-id` will have access to the facility-specific features and pages.
- `+` matches the current facility and all sub-facilities/instruments. For example, if the facility acronym is `MX-ID`,
  and a sub-facility has an acronym `B123` then a user with the role `staff:mx-id` will implicitly also have the role
  `staff:b123`.
- `-` matches the current facility and all parent facilities. For example, if the facility acronym is `MX-ID`,
  and a parent facility has an acronym `MX`, then a user with the role `staff:mx-id` will implicitly also have the role
  `staff:mx`.

USO_FACILITY_ADMIN_ROLES
........................
A string containing the wildcard role template for users considered administrators of a particular facility within
USO system. These users will have access to all management features and pages related to the
facility/beamline/instrument. As a wildcard role, it supports the same syntax as `USO_FACILITY_STAFF_ROLES` above.

USO_HSE_ROLES
.............
A list of strings containing the role names for users considered Health & Safety (HSE) staff members of the USO system.
These users will have access to features and pages related to health and safety, such as managing health and safety
requirements, performing health & safety reviews, and some features of beam time sessions and laboratories. The default
setting is::

    USO_HSE_ROLES = ['staff:hse']


Additional Roles
.................
Additional roles linked to specific features or applications within the USO system can also be configured within
a running instance in several cases. For example:

- **Review Type**: Each Review Type can have a specific role associated with it, which is used to determine who can
  review proposals of that type. This role is configured by the User Office Administrators when creating or editing
  Review Types.
- **Access Pool**: Each Access Pool can have a specific role associated with it, which is used to determine who can
  submit proposals for that pool. This role is configured by the User Office Administrators when creating or editing
  Access Pools.

For each of these roles, the role name is a simple string or a wildcard role for roles used in the context of
"per-facility" features.


ROLEPERMS_DEBUG
...............
A boolean flag that enables or disables the role permissions debugging mode. When set to `True`, the USO system will
log detailed information about role permissions and access checks. This is useful for debugging and troubleshooting
role-based access control issues. The default setting is `False`.

USO_STYLE_OVERRIDES
...................
To customize the appearance of the USO system, you can create a custom CSS file and set the `USO_STYLE_OVERRIDES`
setting in `local/settings.py` to the path of your custom CSS file. This file will be loaded after the default USO styles,
allowing you to override any styles you want. This setting should contain a list of 'css' files, for example::

    USO_STYLE_OVERRIDES = [
        'custom.css',
        'extra-styles.css',
    ]

The custom CSS file should be placed in the `local/media/css` directory of your USO instance.

Profile Managers
----------------
Profile managers can be used to synchronize user profiles with external systems, such as LDAP or other identity
providers. The default profile manager does not perform any synchronization. However, you can implement a custom
profile for your backend system and configure the USO system to use it.

Custom profile managers can override the the following methods:

.. code-block:: python

    from users.profiles import ExternalProfileManager

    class CustomProfileManager(ExternalProfileManager):

        PROFILE_FIELDS = ['first_name', 'last_name', 'email']  # list of fields to sync with the User model

        @classmethod
        def create_username(cls, profile: dict) -> str:
            """
            Create a username from the profile. This is used to create a username for a new user.
            :param profile: dictionary of profile parameters containing first_name and last_name
            :return: unique username string
            """
            ...

        @classmethod
        def fetch_profile(cls, username: str) -> dict:
            """
            Called to fetch a user profile from the remote source. This is used to sync the specified user's
            profile from the remote source to the local database. Only fields specified in PROFILE_FIELDS will be changed in
            the User model.
            :param username: username of the user to fetch
            :return: dictionary of profile parameters
            """
            ...

        @classmethod
        def create_profile(cls, profile: dict) -> dict:
            """
            Called to create a new profile in the remote source. User is expected to not exist in the remote source.
            :param profile: Dictionary of profile parameters.
            """
            ...

        @classmethod
        def update_profile(cls, username, profile: dict, photo=None) -> bool:
            """
            Called to update the profile in the remote source. User is expected to exist in the remote source.

            :param profile: Dictionary of profile parameters.
            :param photo: File-like object of the user's photo
            :param username: username of the user to update
            :return: True if successful, False otherwise.
            """
            ...

        @classmethod
        def fetch_new_users(cls) -> list[dict]:
            """
            Fetch new users from the remote source. This is used to sync new users from the remote source to the local database.
            :return: list of dicts, one per user.
            """
            ...

        @classmethod
        def get_user_photo_url(cls, username: str) -> str:
            """
            Get the URL of the user's profile photo. This is used to display the user's photo in the USO system.
            :param username: username of the user
            :return: URL of the user's profile photo
            """
            ...


To configure profile managers, you can set the following parameters in `local/settings.py` as follows:

.. code-block:: python

    from .custom import CustomProfileManager
    # where custom.py is a module within the `local` directory

    USO_PROFILE_MANAGER = CustomProfileManager


Code Generators
---------------
Within the USO system, some objects such as *Proposals*, *Projects*, *Submissions* and *Materials* use natural keys
available through the `code` attribute. These are unique identifiers that are automatically generated when the object
is created and saved.  The algorithm for generating these codes is defined within various code generator functions
that can be overridden in the `local/settings.py` file.

The default code generators are defined as follows:

.. code-block:: python

   USO_CODE_GENERATORS = {
       'PROPOSAL': 'proposals.utils.generate_proposal_code',
       'PROJECT': 'projects.utils.generate_project_code',
       'SUBMISSION': 'proposals.utils.generate_submission_code',
       'MATERIAL': 'projects.utils.generate_material_code',
   }

You can override these code generators by implementing your own functions to generate codes and replacing the
entry in USO_CODE_GENERATORS with a string representing the path to the module.  Modules placed in the `local`
directory are also available. For example:

.. code-block:: python

    USO_CODE_GENERATORS = {
        'PROPOSAL': 'local.custom.generate_proposal_code',
    }

The above code will replace the default proposal code generator with a custom function defined in the `local/custom.py`
module.

Code generator functions should follow a signature similar to the following:

.. code-block:: python

    def generate_proposal_code(proposal: Proposal) -> str:
        """
        Generate a unique code for the proposal.
        :param proposal: The proposal object for which to generate the code.
        :return: A unique string code for the proposal.
        """
        ...

Objects like *Proposals*, *Projects*, *Submissions* and *Materials* that support this interface, also provide some
helper functions and attributes that may be useful when generating codes. These include:

- `year_index()`: Returns the year index of the object, which is useful for generating codes that increment within the
  year and reset at the start of each year.
- `month_index()`: Returns the index of the object within the month. Resets each month.
- `created`: DateTime object representing the creation time of the object
- `modified`: DateTime object representing the last modification time of the object

The `year_index()` and `month_index()` methods are involve database queries and may be slow for very large datasets.

.. note::
   The code generator functions should return a string that is unique within the scope of the object type. Only
   provide a custom code generator for the object types you want to change. The default code generators will be used
   for the other object types.

.. warning::
   Changing code generators will not change the codes of existing objects. It will only affect new objects created
   after the change. If you want to change the codes of existing objects, you will need to manually update them in the
   database.

