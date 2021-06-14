"""Settings loader used by the Docker container."""

import os.path
import sys

if os.path.isfile("/entrypoint.sh"):
    sys.path.append("/data")

from .prod import *

try:
    from local_settings import *  # isort:skip
except ImportError:
    raise ImportError(
        "Could not import the local settings file. Make sure it has been created "
        "correctly."
    )

if os.environ.get("TUMPARA_HOST") is not None:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, os.environ.get("TUMPARA_HOST")]
