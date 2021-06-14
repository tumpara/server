"""Base tumpara configuration.

In order to run the application, create a new settings file that imports everything
from this file and set it in the DJANGO_SETTINGS_MODULE environment variable.

The following are the minimum additional settings that is required to run:
- SECRET_KEY and DEBUG variables
- Configure a "default" databases in DATABASES. This database must be one of the
  backends supported by GeoDjango.
- Set crossorigin configuration: https://pypi.org/project/django-cors-headers/


See the other configuration files for examples.
"""

import os.path

from PIL import ImageFile

# The base directory (root folder of the tumpara module) is two levels above this file.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# In the docker container, use the /data folder for storage. Otherwise just the working
# directory.
if os.path.isfile("/entrypoint.sh"):
    DATA_DIR = "/data"
else:
    DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

# Logging
# https://docs.djangoproject.com/en/3.0/topics/logging/

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {module} - {message}",
            "style": "{",
        }
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {"level": os.getenv("LOG_LEVEL", "WARNING"), "handlers": ["console"]},
        "django.db.backends": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
        "PIL": {
            "handlers": [],
            "propagate": False,
        },
    },
}


# Application definition

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.spatialite",
        "NAME": os.path.join(DATA_DIR, "db.sqlite3"),
    }
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.gis",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "graphene_django",
    "graphene_gis",
    "tumpara.accounts",
    "tumpara.collections",
    "tumpara.storage",
    "tumpara.timeline",
    "tumpara.multimedia",
    "tumpara.content.gallery",
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "tumpara.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "tumpara.wsgi.application"

AUTH_USER_MODEL = "accounts.user"


# Graphene GraphQL API frontend
# https://docs.graphene-python.org/

GRAPHENE = {
    "SCHEMA": "tumpara.api.schema.root",
    "MIDDLEWARE": [],
    "GRAPHIQL": True,
}


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(DATA_DIR, "static")

# Application settings

# Directories for saving preview caches.
PREVIEW_ROOT = os.path.join(DATA_DIR, "previews")

# Approximate number of total components a blurhash should have.
BLURHASH_SIZE = 12

# Interval between items when the scanner should yield progress reports.
REPORT_INTERVAL = 500

ImageFile.LOAD_TRUNCATED_IMAGES = True
