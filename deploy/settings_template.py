####################################################################################################
# This is a template for the settings.py file. You should copy this file to local/settings.py and
# customize the settings to match your environment. You should customize the settings to
# match your production environment.
####################################################################################################

DEBUG = True                        # Set to False in production
SITE_URL = "http://localhost"       # The URL of the site
ALLOWED_HOSTS = ['*']               # The list of allowed hosts

USO_ADMIN_ROLES = ["administrator:uso", "developer-admin"]
USO_ADMIN_PERMS = []

# SECURITY WARNING: Generate a new key and keep the secret key used in production secret!
SECRET_KEY = 'g`0wamAE>-n-mZ<Ukx-A(*No2DSJ%ov1"I+u77|T_="6%c|HhKOd]~+,,f;)[g3p'


# configure the cache settings
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
        "LOCATION": "cache:11211",
    }
}

# Configure your database settings
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


# Configure your email settings
EMAIL_HOST_USER = "email@email-server.com"
EMAIL_HOST_PASSWORD = "<email-password>"
EMAIL_PORT = 587
EMAIL_HOST = "email-server.com"


# To synchronize roles, permissions and other user attributes from a remote source like a People Database,
# you can subclass RemoteProfileManager and set the appropriate URLs and fields, or you can override the
# methods to customize the behaviour.
from users.profiles import RemoteProfileManager


class PeopleDBProfileManager(RemoteProfileManager):
    PROFILE_FIELDS = ['title', 'first_name', 'last_name', 'preferred_name', 'email', 'username', 'roles', 'permissions']
    USER_PHOTO_URL = "http://opi2051-002.clsi.ca:9000/media/idphoto/{username}.jpg"
    USER_PROFILE_URL = 'http://opi2051-002.clsi.ca:9000/api/v1/people/{username}/'
    USER_CREATE_URL = 'http://opi2051-002.clsi.ca:9000/api/v1/people/'
    USER_LIST_URL = 'http://opi2051-002.clsi.ca:9000/api/v1/new-staff/'
    API_HEADERS = {}


# Set the PROFILE_MANAGER to the custom profile manager you would like to use. By default
# a dummy profile manager is used that does not synchronize any user attributes.

# PROFILE_MANAGER = PeopleDBProfileManager
