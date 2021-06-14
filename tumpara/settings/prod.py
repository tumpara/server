"""Base tumpara configuration for production use."""

from . import *

DEBUG = False

ALLOWED_HOSTS = []


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


# Disable it for now, since we refer to it in the documentation, although we should
# enable it again once it's possible to install custom plugins.
# # Hardened GraphQL configuration
# GRAPHENE["GRAPHIQL"] = False
# GRAPHENE["MIDDLEWARE"] += [
#     "tumpara.api.util.DisableIntrospectionMiddleware",
# ]
