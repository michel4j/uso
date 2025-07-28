####################################################################################################
# This is a template for the settings.py file. You should copy this file to local/settings.py and
# customize the settings to match your environment. All settings changes should be done in this
# file rather than usonline/settings.py. The file should not be readable by the public, so
# it should be placed in a directory that is not accessible by anyone other than the web server
####################################################################################################


DEBUG = True                        # Set to False in production
SITE_URL = "http://localhost:8080"  # The URL of the site
ALLOWED_HOSTS = ["localhost", '*']  # The list of allowed hosts


# -----------------------------------------------------------------------------
# SECURITY WARNING: Generate a new key and keep the secret key used in production secret!
# -----------------------------------------------------------------------------
SECRET_KEY = 'g`0wamAE>-n-mZ<Ukx-A(*No2DSJ%ov1"I+u77|T_="6%c|HhKOd]~+,,f;)[g3p'
USO_STYLE_OVERRIDES = []    # list of CSS files to override the default styles, place files in local/media/css/

# -----------------------------------------------------------------------------
# Configure the weather applet settings
# Please register at https://openweathermap.org/api to get your own free version 2.5 API key
# -----------------------------------------------------------------------------
USO_WEATHER_LOCATION = [52.0936, -106.5552]     # Set your location (lat, lon) for weather data
USO_OPEN_WEATHER_KEY = ""                       # Open Weather API key for weather data


# -----------------------------------------------------------------------------
# Google API key for Google Maps, Geocoding, and other Google services used
# in the publications application.
# Please register at https://developers.google.com/maps/documentation/javascript/get-api-key
# -----------------------------------------------------------------------------
# GOOGLE_API_KEY = ""

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
        'PASSWORD': 'Baev6Aegha&p2iedie#Qu6Jooz5eNg7Z',  # Change this to your database password
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
# EMAIL_HOST_PASSWORD = "<email-password>"
# EMAIL_PORT = 587
# EMAIL_HOST = "email-server.com"

# -----------------------------------------------------------------------------
# Configure roles
# -----------------------------------------------------------------------------
# USO_ADMIN_ROLES = ["admin:uso", "staff"]    # The superuser roles
# USO_ADMIN_PERMS = []                                                      # The superuser permissions
# ROLEPERMS_DEBUG = False                                                   # Print permissions and roles debug info

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
# Configure Facilities for fetching PDB entries
# The key is the PDB ID in the format {SITE}{BEAMLINE}.  The value is a list of local facility acronyms to credit for
# each PDB entry in that category. For example:
# USO_PDB_FACILITIES = {
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
# USO_STYLE_OVERRIDES = [
#    'custom.css'
# ]