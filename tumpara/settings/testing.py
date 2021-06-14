import logging

from .dev import *


class GraphQLLogFilter(logging.Filter):
    """Filter out GraphQL client errors that are intentional."""

    def filter(self, record):
        if (
            record.name == "graphql.execution.executor"
            and record.funcName == "resolve_or_error"
        ):
            return False
        if (
            record.name == "graphql.execution.utils"
            and record.msg
            and "GraphQLLocatedError" in record.msg
        ):
            return False
        return True


# Force an in-memory test database (since we are testing with SQLite). Pytest
# normally automatically does it, but not currently when using xdist with a
# spaciallite database. See here: https://github.com/pytest-dev/pytest-django/issues/88
DATABASES["default"]["TEST"] = {"NAME": ":memory:"}

# Add a filter that hides GraphQL client logs because they are pretty noisy,
# especially when using hypothesis. See here:
# https://github.com/graphql-python/graphene/issues/513#issuecomment-486313001
LOGGING["filters"]["graphql_log_filter"] = {"()": GraphQLLogFilter}
LOGGING["loggers"]["graphql.execution.executor"] = {
    "level": "WARNING",
    "handlers": ["console"],
    "filters": ["graphql_log_filter"],
}
LOGGING["loggers"]["graphql.execution.utils"] = LOGGING["loggers"][
    "graphql.execution.executor"
]

# Downgrade to a faster password hasher during testing to speed up the process.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
