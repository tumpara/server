import pytest
from graphene.test import Client

from .utils import DjangoHypothesisExecutor


@pytest.fixture(scope="session")
def graphql_client() -> Client:
    from tumpara.api.schema import root

    return Client(root)


@pytest.fixture(scope="function")
def django_executor(django_db_setup, django_db_blocker):
    """This method the aforementioned executor in a pytest fixture.

    In order to function, this must be defined as the first argument to a test function.
    """
    return DjangoHypothesisExecutor()
