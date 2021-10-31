from graphene.relay.node import to_global_id
from graphene.test import Client
from hypothesis import HealthCheck, given, settings

from tumpara.accounts import api as accounts_api
from tumpara.accounts.models import AnonymousUser, User
from tumpara.testing import FakeRequestContext
from tumpara.testing import strategies as st

get_users_query = """
    fragment UserFields on User {
        username
        firstName
        lastName
        email
        id
    }
    query GetUsers {
        me {
            ...UserFields
        }
        users(first: 100) {
            edges {
                node {
                    ...UserFields
                }
            }
        }
    }
"""

get_user_by_id_query = """
    query GetUserById($id: ID!) {
        node(id: $id) {
            ...on User {
                username
                firstName
                lastName
                email
            }
        }
    }
"""


@st.composite
def dataset_strategy(draw: st.DrawFn):
    draw(
        st.sets(
            st.from_model(User, is_staff=st.just(False), is_superuser=st.just(False)),
            min_size=1,
            max_size=5,
        )
    )
    draw(
        st.sets(
            st.superusers(),
            min_size=1,
            max_size=5,
        )
    )


@settings(
    max_examples=40,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(dataset_strategy(), st.data())
def test_anonymous_user_queries(
    django_executor, graphql_client: Client, dataset, data: st.DataObject
):
    """Anonymous users cannot query the user list."""
    result = graphql_client.execute(
        get_users_query, context=FakeRequestContext(user=AnonymousUser())
    )
    assert "errors" not in result
    assert result["data"]["me"] is None
    assert len(result["data"]["users"]["edges"]) == 0

    users = list(User.objects.filter(is_superuser=False))
    superusers = list(User.objects.filter(is_superuser=True))

    # Check direct user accessing.
    for user in {
        data.draw(st.sampled_from(users)),
        data.draw(st.sampled_from(superusers)),
    }:
        result = graphql_client.execute(
            get_user_by_id_query,
            context=FakeRequestContext(user=AnonymousUser()),
            variables={"id": to_global_id(accounts_api.User._meta.name, user.pk)},
        )
        assert "errors" not in result
        assert result["data"]["node"] is None


def check_user_api_response(response: dict, user: User, private_fields: bool = False):
    assert response["username"] == user.username
    assert response["firstName"] == user.first_name
    assert response["lastName"] == user.last_name
    if private_fields:
        assert response["email"] == user.email
    else:
        assert response["email"] is None


@settings(
    max_examples=40,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(dataset_strategy(), st.data())
def test_regular_user_queries(
    django_executor, graphql_client: Client, dataset, data: st.DataObject
):
    """Logged-in users may see the entire user list, but not private fields like
    email."""
    users = list(User.objects.filter(is_superuser=False))
    superusers = list(User.objects.filter(is_superuser=True))
    logged_in_user = data.draw(st.sampled_from(users))

    result = graphql_client.execute(
        get_users_query, context=FakeRequestContext(user=logged_in_user)
    )
    assert "errors" not in result
    check_user_api_response(result["data"]["me"], logged_in_user, True)

    assert len(result["data"]["users"]["edges"]) == len(users) + len(superusers)
    for user_edge in result["data"]["users"]["edges"]:
        user_node = user_edge["node"]
        user = User.objects.get(username=user_node["username"])
        check_user_api_response(user_node, user, user == logged_in_user)

    # Check direct user accessing.
    for user in {
        data.draw(st.sampled_from(users)),
        data.draw(st.sampled_from(superusers)),
    }:
        result = graphql_client.execute(
            get_user_by_id_query,
            context=FakeRequestContext(user=logged_in_user),
            variables={"id": to_global_id(accounts_api.User._meta.name, user.pk)},
        )
        assert "errors" not in result
        check_user_api_response(result["data"]["node"], user, user == logged_in_user)


@settings(
    max_examples=40,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    print_blob=True,
)
@given(dataset_strategy(), st.data())
def test_superuser_user_queries(
    django_executor,
    graphql_client: Client,
    dataset,
    data: st.DataObject,
):
    """Superusers may see the complete user list."""
    users = list(User.objects.filter(is_superuser=False))
    superusers = list(User.objects.filter(is_superuser=True))
    logged_in_user = data.draw(st.sampled_from(superusers))
    result = graphql_client.execute(
        get_users_query, context=FakeRequestContext(user=logged_in_user)
    )
    assert "errors" not in result

    check_user_api_response(result["data"]["me"], logged_in_user, True)

    assert len(result["data"]["users"]["edges"]) == len(users) + len(superusers)
    for user_edge in result["data"]["users"]["edges"]:
        user_node = user_edge["node"]
        user = User.objects.get(username=user_node["username"])
        check_user_api_response(user_node, user, True)

    # Check direct user accessing.
    for user in {
        data.draw(st.sampled_from(users)),
        data.draw(st.sampled_from(superusers)),
    }:
        result = graphql_client.execute(
            get_user_by_id_query,
            context=FakeRequestContext(user=user),
            variables={"id": to_global_id(accounts_api.User._meta.name, user.pk)},
        )
        assert "errors" not in result
        check_user_api_response(result["data"]["node"], user, True)
