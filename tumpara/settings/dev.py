from . import *

SECRET_KEY = "thisisnotsecure"
DEBUG = True

# An empty allowed hosts config will allow connections to localhost when DEBUG is
# active. See: https://docs.djangoproject.com/en/3.1/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []

# Disable password validators in development mode.
AUTH_PASSWORD_VALIDATORS = []

# Effectively disable all crossorigin headers.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Enable the GraphQL debug middleware.
GRAPHENE["MIDDLEWARE"] += [
    "graphene_django.debug.DjangoDebugMiddleware",
]
