"""conftest.py

Configuration file for pytest. Create a file with the same name in the directory of your
tests and import this module to activate these test settings.
"""

import os

import hypothesis
from hypothesis import HealthCheck

from .fixtures import *  # noqa: F401 (this module registers fixtures)

hypothesis.settings.register_profile(
    "dev",
    max_examples=100,
    verbosity=hypothesis.Verbosity.verbose,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
hypothesis.settings.register_profile(
    "dev_lite",
    max_examples=40,
    verbosity=hypothesis.Verbosity.verbose,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
hypothesis.settings.register_profile(
    "ci",
    max_examples=500,
    verbosity=hypothesis.Verbosity.normal,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
hypothesis.settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))
