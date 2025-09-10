"""
Django settings for usonline project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

import os
import sys
from pathlib import Path

from django.conf import global_settings
from Crypto.Random import get_random_bytes


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
PROJECT_DIR = Path(__file__).parent
BASE_DIR = PROJECT_DIR.parent
LOCAL_DIR = BASE_DIR / 'local'
APPS_DIR = BASE_DIR / 'apps'
[sys.path.append(str(path)) for path in [APPS_DIR, BASE_DIR, LOCAL_DIR] if path not in sys.path]


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '5ni&$-wok-8w3_my-#@08s)hcwed^2xy3-m9_0tpt-le4j-926'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []
INTERNAL_IPS = [
    '127.0.0.1/32', '::1/128', 'localhost'  # Allow localhost and IPv6 localhost
]

INTERNAL_URLS = ('^/admin',)
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.postgres',
    'formtools',
    "itemlist",
    "crispy_forms",
    "crispy_bootstrap5",
    "crisp_modals",
    'dynforms',
    'reportcraft',
    'users',
    'roleperms',
    'notifier',
    'isocron',
    'proposals',
    'projects',
    'misc',
    'django_cas_ng',
    'proxy',
    'rest_framework',
    'beamlines',
    'samples',
    'publications',
    'scheduler',
    'weather',
    'surveys',
    'agreements',
    'dynamic_breadcrumbs',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = global_settings.AUTHENTICATION_BACKENDS + [
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_USER_MODEL = 'users.User'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PROJECT_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request',
                "dynamic_breadcrumbs.context_processors.breadcrumbs",
            ],
        },
    },
]

ROOT_URLCONF = 'usonline.urls'
WSGI_APPLICATION = 'usonline.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases
#

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'local', 'usonline.db'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en'
TIME_ZONE = 'America/Regina'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [
    os.path.join(PROJECT_DIR, "static"),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'local/media')

# django-rest-framework docs at www.django-rest-framework.org
REST_FRAMEWORK = {
    'DEFAULT_MODEL_SERIALIZER_CLASS':
        'rest_framework.serializers.HyperlinkedModelSerializer',

    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
    ],
}

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_URL = '/logout/'
LOGOUT_REDIRECT_URL = '/login/'

DEFAULT_FROM_EMAIL = "noreply@example.com"
SERVER_EMAIL = "noreply@example.com"
ADMINS = (
    ('Admin', 'admin@example.com'),
)
EMAIL_SUBJECT_PREFIX = '[USO] '


SITE_URL = "http://localhost:8080"
CAS_SERVER_URL = "https://cas.example.com/cas/"
CAS_SERVICE_DESCRIPTION = "User Services Online"
CAS_LOGOUT_COMPLETELY = True
CAS_SINGLE_SIGN_OUT = True
CAS_VERSION = 3
CAS_CREATE_USER = False
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


from django.core.serializers import register_serializer
register_serializer('yml', 'django.core.serializers.pyyaml')

from users.profiles import ExternalProfileManager

USO_DEFAULT_CODE_GENERATORS = {
    'PROPOSAL': 'proposals.utils.generate_proposal_code',
    'PROJECT': 'projects.utils.generate_project_code',
    'SUBMISSION': 'proposals.utils.generate_submission_code',
    'MATERIAL': 'projects.utils.generate_material_code',
}
USO_CODE_GENERATORS = {}   # override this in local.settings.py to add custom code generators for various objects

# ROLES
USO_ADMIN_ROLES = ["admin:uso"]
USO_CONTRACTS_ROLES = ["staff:contracts"]
USO_CURATOR_ROLES = ["curator:publications"]
USO_HSE_ROLES = ["staff:hse"]
USO_MANAGER_ROLES = ["manager:science"]
USO_REVIEWER_ROLES = ["reviewer"]
USO_STAFF_ROLES = ["admin", "staff"]
USO_STUDENT_ROLES = ["student"]
USO_USER_ROLES = ["user"]
USO_FACILITY_ADMIN_ROLE = 'admin:-'     # role templates '-' means propagate down subunits, '*' means don't propagate
USO_FACILITY_STAFF_ROLE = 'staff:-'     # '+' means propagate up subunits
USO_ONSITE_USER_PERMISSION = '{}-USER'
USO_REMOTE_USER_PERMISSION = '{}-REMOTE-USER'
USO_FACILITY_ACCESS_PERMISSION = 'FACILITY-ACCESS'

USO_ASSIGNABLE_ROLES = [
    {'role': 'user'},
    {'role': 'reviewer'},
    {'role': 'contractor'},
    {'role': 'beam-team:+', 'per-facility': True},
]



USO_STYLE_OVERRIDES = []
USO_THROTTLE_KEY = get_random_bytes(16)
USO_ADMIN_PERMS = []
USO_OPEN_WEATHER_KEY = ""
USO_WEATHER_LOCATION = [52.14, -106.63]  # Default to CLSI
USO_PROFILE_MANAGER = ExternalProfileManager
USO_REVIEW_ASSIGNMENT = "MIP"    # or either "MIP" or "CMACRA" or "BRUTE_FORCE"
USO_PDB_SITE = 'XXXX'       # Protein Data Bank site code
USO_PDB_SITE_MAP = {
}

OPEN_CITATIONS_API_KEY = None
CROSSREF_THROTTLE = 1  # time delay between crossref calls
CROSSREF_BATCH_SIZE = 20
CROSSREF_API_EMAIL = None


ROLEPERMS_DEBUG = False
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', None)
DYNAMIC_BREADCRUMBS_PATH_MAX_DEPTH = 8
DYNFORMS_MIXINS = {
    'VIEW': ['roleperms.views.AdminRequiredMixin'],
    'EDIT': ['roleperms.views.AdminRequiredMixin'],
}
REPORTCRAFT_MIXINS = {
    'VIEW': ['roleperms.views.StaffRequiredMixin'],
    'EDIT': ['roleperms.views.AdminRequiredMixin'],
}
REPORTCRAFT_FUNCTIONS = [
    'misc.functions.String',
    'misc.functions.JoinArray',
    'misc.functions.ArrayLength',
    'reportcraft.functions.postgres.Join',
    'django.contrib.postgres.aggregates.ArrayAgg',
    'django.contrib.postgres.aggregates.JSONBAgg',
    'misc.functions.ArrayItems',
    'misc.functions.JSONAvg',
    'misc.functions.JSONStd',
    'misc.functions.JSONSum',
    'misc.functions.JSONMin',
    'misc.functions.JSONMax',
]

REPORTCRAFT_APPS = [
    'proposals',
    'projects',
    'samples',
    'publications',
    'scheduler',
    'surveys',
    'users',
]

# -----------------------------------------------------------------------------
# Load local settings if available
try:
    from local.settings import *
except ImportError:
    import logging
    logging.debug("No local/settings.py, using settings.py only.")

# version number
with open(os.path.join(BASE_DIR, 'VERSION'), 'r') as fobj:
    VERSION = fobj.read().strip()

# Register custom code generators
USO_CODE_GENERATORS = {
    **USO_DEFAULT_CODE_GENERATORS,
    **USO_CODE_GENERATORS
}

CSRF_TRUSTED_ORIGINS = [SITE_URL]

