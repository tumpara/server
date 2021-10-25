"""Base Tumpara settings.

This will make the app run and load settings from environment variables
"""

import os
from pathlib import Path
from typing import Callable, Optional, Type, TypeVar, Union, overload

from django.core.exceptions import ImproperlyConfigured
from PIL import ImageFile

DefaultValue = TypeVar("DefaultValue")
T = TypeVar("T")


@overload
def parse_env(
    variable_name: str, default_value: DefaultValue, cast: None
) -> Union[DefaultValue, str]:
    ...


@overload
def parse_env(
    variable_name: str, default_value: DefaultValue, cast: Callable[[str], T]
) -> Union[DefaultValue, T]:
    ...


@overload
def parse_env(
    variable_name: str, default_value: DefaultValue, cast: Type[bool]
) -> Union[DefaultValue, bool]:
    ...


def parse_env(
    variable_name: str,
    default_value: Optional[DefaultValue] = None,
    cast: Union[None, Type[bool], Callable[[str], T]] = None,
) -> Union[None, DefaultValue, str, bool, T]:
    if variable_name not in os.environ:
        return default_value

    value = os.environ[variable_name]
    if cast is None:
        return value
    if cast is bool:
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        elif value.lower() in ("false", "no", "0", "off"):
            return False
        else:
            raise ImproperlyConfigured(
                f"Failed to parse settings option {value!r} from environment variable "
                f"{variable_name} as a boolean. Please check your formatting (values "
                f'can be stated with "True" and "False").'
            )

    try:
        return cast(value)
    except ValueError:
        raise ImproperlyConfigured(
            f"Failed to parse settings option {value!r} from environment "
            f"variable {variable_name}. Please check your formatting (should "
            f"have type {cast.__name__})."
        )


def string_or_none(value):
    if value is None:
        return None
    value = str(value)
    if len(value) == 0:
        return None
    return value


if "TUMPARA_DATA_ROOT" in os.environ:
    DATA_ROOT = Path(os.environ["TUMPARA_DATA_ROOT"])
elif Path("/opt/tumpara/entrypoint.sh").is_file():
    # Inside the Docker container, we use '/data' as the default data folder, because
    # that is also exposed as a volume.
    DATA_ROOT = Path("/data")
else:
    # For other installs, the default is a directory named 'data' inside the project
    # root. This is used - for example - for git-based installs.
    #                                ↱ settings/
    #                                ╎      ↱ tumpara/
    #                                ╎      ╎      ↱ The project root
    MODULE_PARENT = Path(__file__).parent.parent.parent
    if MODULE_PARENT.name == "site-packages":
        # If the module's parent folder is called 'site-packages', then the app is
        # probably installed system-wide (or in a virtualenv) using a package manger.
        # In that case, it's probably not desired to populate Python's system folder
        # with our data, so we bail and force the user to configure it manually.
        raise ImproperlyConfigured(
            "Could not automatically determine a data directory to use. Please set the "
            "TUMPARA_DATA_ROOT environment variable manually."
        )
    DATA_ROOT = MODULE_PARENT / "data"

if not DATA_ROOT.exists():
    try:
        DATA_ROOT.mkdir()
    except IOError:
        raise ImproperlyConfigured(
            f"Failed to create the data directory at '{DATA_ROOT}'. Make sure the "
            f"parent is writable."
        )
elif not DATA_ROOT.is_dir():
    raise ImproperlyConfigured(
        f"The data directory '{DATA_ROOT}' exists but is not a folder. Please delete "
        f"if there is already a file with that name."
    )


# -- Django settings -------------------------------------------------------------------

if "TUMPARA_SECRET_KEY" in os.environ:
    SECRET_KEY = os.environ["TUMPARA_SECRET_KEY"]
    del os.environ["TUMPARA_SECRET_KEY"]


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
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {
            "level": os.environ.get("LOG_LEVEL", "INFO"),
            "handlers": ["console"],
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": os.environ.get("LOG_LEVEL", "WARNING"),
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
        "NAME": DATA_ROOT / "db.sqlite3",
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

ALLOWED_HOSTS = parse_env("TUMPARA_HOST", list[str](), lambda host: [host])

AUTH_USER_MODEL = "accounts.user"


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Graphene GraphQL API frontend
# https://docs.graphene-python.org/

GRAPHENE_MIDDLEWARE: list[str] = []
GRAPHENE = {
    "SCHEMA": "tumpara.api.schema.root",
    "MIDDLEWARE": GRAPHENE_MIDDLEWARE,
    "GRAPHIQL": True,
}

if parse_env("TUMPARA_HARDENED_GRAPHQL", False, bool):
    GRAPHENE["GRAPHIQL"] = False
    GRAPHENE_MIDDLEWARE += [
        "tumpara.api.util.DisableIntrospectionMiddleware",
    ]


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
STATIC_ROOT = DATA_ROOT / "static"


# -- Tumpara-specific options ----------------------------------------------------------

# Directories for saving preview caches.
PREVIEW_ROOT = DATA_ROOT / "previews"

# Approximate number of total components a blurhash should have.
BLURHASH_SIZE = parse_env("TUMPARA_BLURHASH_SIZE", 12, int)

# Interval between items when the scanner should yield progress reports.
REPORT_INTERVAL = parse_env("TUMPARA_REPORT_INTERVAL", 500, int)

# Whether to enable the 'demo://' storage backend.
ENABLE_DEMO_BACKEND = parse_env("TUMPARA_ENABLE_DEMO_BACKEND", False, bool)

# If a file in a folder exists with this name the entire folder will be recursively
# ignored while scanning.
DIRECTORY_IGNORE_FILENAME = parse_env(
    "TUMPARA_DIRECTORY_IGNORE_FILENAME", ".nomedia", string_or_none
)

ImageFile.LOAD_TRUNCATED_IMAGES = True
