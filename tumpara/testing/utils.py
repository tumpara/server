import shutil
from dataclasses import dataclass

import graphene
import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from hypothesis import HealthCheck
from hypothesis import settings as Settings
from hypothesis.stateful import run_state_machine_as_test
from pytest_django.plugin import _blocking_manager as django_db_blocking_manager

from tumpara.accounts.models import GenericUser


@dataclass
class FakeRequestContext:
    user: GenericUser


class FakeResolveInfo(graphene.ResolveInfo):
    """Fake Graphene resolve info which yields the actual GraphQL schema.

    The constructor takes keyword arguments which will be passed to the fake request
    context.
    """

    def __init__(self, **kwargs):
        from tumpara.api import schema

        kwargs.setdefault("user", AnonymousUser())

        super().__init__(
            field_name="",
            field_asts=[],
            return_type=None,
            parent_type=None,
            schema=schema.root,
            fragments={},
            root_value=None,
            operation=None,
            variable_values={},
            context=FakeRequestContext(**kwargs),
        )


class DjangoHypothesisExecutor:
    """Hypothesis executor that takes care of Django database transactions between
    runs and clears the preview cache."""

    def __init__(self):
        self.test_case = TestCase(methodName="__init__")

    @staticmethod
    def _clean_previews():
        try:
            shutil.rmtree(settings.PREVIEW_ROOT)
        except FileNotFoundError:
            pass

    def setup_example(self, *args, **kwargs):
        self._clean_previews()
        django_db_blocking_manager.unblock()
        self.test_case._pre_setup()

    def teardown_example(self, *args, **kwargs):
        self._clean_previews()
        self.test_case._post_teardown()
        django_db_blocking_manager.restore()


def state_machine_to_test_function(
    state_machine_class,
    *,
    use_django_executor=False,
    disable_migrations=False,
    settings={},
):
    if use_django_executor:
        executor = DjangoHypothesisExecutor()

        class DjangoRuleBasedStateMachine(state_machine_class):
            @staticmethod
            def setup_example(*args, **kwargs):
                executor.setup_example(*args, **kwargs)

            @staticmethod
            def teardown_example(*args, **kwargs):
                executor.teardown_example(*args, **kwargs)

        state_machine_class = DjangoRuleBasedStateMachine

    @pytest.mark.usefixtures("django_db_setup", "django_db_blocker")
    def run_as_test():
        run_state_machine_as_test(
            state_machine_class,
            settings=Settings(
                deadline=None, suppress_health_check=HealthCheck.all(), **settings
            ),
        )

    return run_as_test
