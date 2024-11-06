# This file is used to store the settings for the local environment.
# Rename to settings.py in the local package and update the settings as needed.

# Secret Key, used for cryptographic signing. Generate a new key for each deployed instance.
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-$&ohhwpn7#4(q@l(pv)y6=-wuolioif3kl6h6(@yo-mw-wp@e^'

# Debug - Enable debug mode, set to False in production
DEBUG = True

# Site URL - The URL of the site
SITE_URL = "http://uso.example.com"

# People Database Photo Source - The URL of the photo source
PHOTO_SRC = "http://people.example.com/photos/"

# People Database API - The URL of the people database API
PEOPLE_DB_API = "http://people.example.com/api/v1/"

# CAS Server URL - The URL of the CAS server
CAS_SERVER_URL = "https://cas.example.com/cas/"

# Cache settings, default is no local memory cache.
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
#         "LOCATION": "127.0.0.1:11211",
#     }
# }

# Database settings, update accordingly. The default is a SQLite database.
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'uso-db',
#         'USER': 'db-user',
#         'PASSWORD': 'db-passwd',
#         'HOST': 'db-host',
#         'PORT': '',
#     }
# }
