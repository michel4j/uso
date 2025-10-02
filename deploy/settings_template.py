####################################################################################################
# This is a template for the settings.py file. You should copy this file to local/settings.py and
# customize the settings to match your environment. All settings changes should be done in this
# file rather than usonline/settings.py. The file should not be readable by the public, so
# it should be placed in a directory that is not accessible by anyone other than the web server
####################################################################################################

import os

# -----------------------------------------------------------------------------
# in a development environment, place the environment in local/.env then install dotenv
# and uncomment the following lines to load the environment variables.
# $ pip install python-dotenv
# -----------------------------------------------------------------------------
# from dotenv import load_dotenv
# load_dotenv()
# -----------------------------------------------------------------------------

DEBUG = False                        # Set to False in production
TIME_ZONE = 'America/Regina'         # Set to your local time zone
SERVER_NAME = os.environ.get('USO_SERVER_NAME', 'localhost')
SERVER_PORT = os.environ.get('USO_SERVER_PORT', 8080)
SITE_URL = f"http://{SERVER_NAME}:{SERVER_PORT}"  # The URL of the site
ALLOWED_HOSTS = ['localhost', '*', 'proxy', SERVER_NAME]  # The list of allowed hosts
CSRF_TRUSTED_ORIGINS = [
    f"http://{SERVER_NAME}",
    f"https://{SERVER_NAME}",
    "http://localhost"
]


# -----------------------------------------------------------------------------
# SECRET_KEY is a crucial security setting used for cryptographic signing within
# Django applications. It is essential to keep this key secret in production.
# SECURITY WARNING: the key used in production secret! A random value should be
# generated and set in the .env variable `SECRET_KEY`. The key below
#  You can generate a new key using Django's
# `django-admin shell` command:
# >>> from django.core.management import utils
# >>> print(utils.get_random_secret_key())
# -----------------------------------------------------------------------------
SECRET_KEY = os.getenv('SECRET_KEY')

# -----------------------------------------------------------------------------
# Configure the weather applet settings
# Please register at https://openweathermap.org/api to get your own free version 2.5 API key
# -----------------------------------------------------------------------------
USO_WEATHER_LOCATION = [52.0936, -106.5552]     # Set your location (lat, lon) for weather data
USO_OPEN_WEATHER_KEY = os.getenv("OPEN_WEATHER_API_KEY")  # OpenWeather API key for weather data

# -----------------------------------------------------------------------------
# Google API key for Google services used in the publications application.
# Please register at https://developers.google.com/maps/documentation/javascript/get-api-key
# -----------------------------------------------------------------------------
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# -----------------------------------------------------------------------------
# Configure the cache settings
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
        "LOCATION": "cache:11211",
    }
}

# -----------------------------------------------------------------------------
# Configure your database settings, these settings are for a the default
# PostgreSQL database, you can change them to match your environment if using
# a different database.
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Configure style overrides
# -----------------------------------------------------------------------------
# USO_STYLE_OVERRIDES = ['custom.css'] # List of CSS files to override the default styles,
#                                      # place files in local/media/css/

# -----------------------------------------------------------------------------
# Configure email server settings, otherwise email notifications will not work
# -----------------------------------------------------------------------------
# EMAIL_HOST_USER = "email@email-server.com"
# EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD'),
# EMAIL_PORT = 587
# EMAIL_HOST = "email-server.com"
# DEFAULT_FROM_EMAIL = "noreply@example.com"    # emails will be sent from this address
# SERVER_EMAIL = "noreply@example.com"          # source of error emails from USO
# ADMINS = [
#     ("John", "john@example.com"),
#     ("Mary", "mary@example.com")
# ]                                 # List of admins to receive error emails
# -----------------------------------------------------------------------------
# Configure roles
# -----------------------------------------------------------------------------
# USO_ADMIN_ROLES = ["admin:uso"]  # The superuser roles
# USO_ADMIN_PERMS = []                      # The superuser permissions
# ROLEPERMS_DEBUG = False                   # Print permissions and roles debug info

# -----------------------------------------------------------------------------
# To synchronize roles, permissions, and other user attributes from a remote source like a People Database,
# you can subclass RemoteProfileManager and set the appropriate URLs and fields, or you can override the
# methods to customize the behaviour.
# -----------------------------------------------------------------------------
# from users.profiles import RemoteProfileManager
#
#
# class PeopleDBProfileManager(RemoteProfileManager):
#     PROFILE_FIELDS = [
#       'title', 'first_name', 'last_name', 'preferred_name', 'email', 'username', 'roles', 'permissions'
#     ]
#     USER_PHOTO_URL = "http://people-db-host/media/idphoto/{username}.jpg"
#     USER_PROFILE_URL = 'http://people-db-host/api/v1/people/{username}/'
#     USER_CREATE_URL = 'http://people-db-host/api/v1/people/'
#     USER_LIST_URL = 'http://people-db-host/api/v1/new-staff/'
#     API_HEADERS = {}
# -----------------------------------------------------------------------------
# USO_PROFILE_MANAGER = PeopleDBProfileManager
# -----------------------------------------------------------------------------
# Configure CROSSREF and Protein Data Bank Settings

CROSSREF_THROTTLE = 1   # time delay between crossref calls
CROSSREF_BATCH_SIZE = 20
CROSSREF_API_EMAIL = os.getenv('CROSSREF_API_EMAIL')
OPEN_CITATIONS_API_KEY = os.getenv('OPEN_CITATIONS_API_KEY')  # OpenCitations API key for citation data

# The key is the PDB ID in the format {SITE}{BEAMLINE}.  The value is a list of local facility acronyms to credit for
# each PDB entry in that category. For example:

USO_PDB_SITE = 'CLSI'       # Protein Data Bank site code
# USO_PDB_SITE_MAP = {
#     "CLSI08B1-1": ["CMCF-ID"],
#     "CLSI08ID-1": ["CMCF-BM"],
#     "CLSIUNKNOWN": ["CMCF-ID", "CMCF-BM"],
# }
# -----------------------------------------------------------------------------
# Override code generators for Projects, Proposals, Submissions, and Materials
# These are the default code generators, you can override any or all of them:
# The dictionary values should be the full path to the function that generates
# the code. function should take a single argument, which is the instance and return a string.
# -----------------------------------------------------------------------------
# USO_CODE_GENERATORS = {
#     'PROPOSAL': 'proposals.utils.generate_proposal_code',
#     'PROJECT': 'projects.utils.generate_project_code',
#     'SUBMISSION': 'proposals.utils.generate_submission_code',
#     'MATERIAL': 'projects.utils.generate_material_code',
# }

# -----------------------------------------------------------------------------
# Configure css files to override the default styles
# Place the CSS files in local/media/css/
# -----------------------------------------------------------------------------
USO_STYLE_OVERRIDES = [
   'custom.css'
]
