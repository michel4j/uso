####################################################################################################
# This is a template for the settings.py file. You should copy this file to local/settings.py and
# customize the settings to match your environment. You should customize the settings to
# match your production environment.
####################################################################################################


DEBUG = True                        # Set to False in production
SITE_URL = "http://localhost:8080"  # The URL of the site
ALLOWED_HOSTS = ["localhost", '*']  # The list of allowed hosts


# SECURITY WARNING: Generate a new key and keep the secret key used in production secret!
# ---
SECRET_KEY = 'g`0wamAE>-n-mZ<Ukx-A(*No2DSJ%ov1"I+u77|T_="6%c|HhKOd]~+,,f;)[g3p'
USO_OPEN_WEATHER_KEY = ""   # Please register at https://openweathermap.org/api to get your own API key for version 2.5
USO_STYLE_OVERRIDES = []    # list of css files to override the default styles, place files in local/media/css/

# Configure the cache settings
# ---
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
        "LOCATION": "cache:11211",
    }
}

# Configure your database settings
# ---
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
# USO_STYLE_OVERRIDES = ['custom.css']  # List of CSS files to override the default styles, place files in local/media/css/

# Configure email server settings, otherwise email notifications will not work
# ---
# EMAIL_HOST_USER = "email@email-server.com"
# EMAIL_HOST_PASSWORD = "<email-password>"
# EMAIL_PORT = 587
# EMAIL_HOST = "email-server.com"

# -----------------------------------------------------------------------------
# Other config settings
# -----------------------------------------------------------------------------
# USO_ADMIN_ROLES = ["admin:uso", "staff"]    # The superuser roles
# USO_ADMIN_PERMS = []                                                      # The superuser permissions
# USO_OPEN_WEATHER_KEY = "fc083799c6457d859764913163f6b584"                 # OpenWeather API key for weather data
# ROLEPERMS_DEBUG = False                                                   # Print permissions and roles debug info


# To synchronize roles, permissions and other user attributes from a remote source like a People Database,
# you can subclass RemoteProfileManager and set the appropriate URLs and fields, or you can override the
# methods to customize the behaviour.
# ---
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
#
# USO_PROFILE_MANAGER = PeopleDBProfileManager


# Configure Facilities for fetching PDB entries
# The key is the PDB ID in the format {SITE}{BEAMLINE}.  The value is a list of local facility acronyms to credit for
# each PDB entry in that category. For example:
# ---
# USO_PDB_FACILITIES = {
#     "CLSI08B1-1": ["CMCF-ID"],
#     "CLSI08ID-1": ["CMCF-BM"],
#     "CLSIUNKNOWN": ["CMCF-ID", "CMCF-BM"],
# }
