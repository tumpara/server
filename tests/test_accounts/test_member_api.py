from graphene.relay.node import to_global_id
from graphene.test import Client
from hypothesis import assume, given, settings

from tumpara.accounts import api as accounts_api
from tumpara.accounts.models import AnonymousUser, GenericUser, User
from tumpara.testing import FakeRequestContext
from tumpara.testing import strategies as st

from . import api
from .models import JoinableThing

set_membership_mutation = """
    mutation SetMembership($host: ID!, $subject: ID!, $owner: Boolean) {
        setMembership(
            input: {
                hostId: $host,
                subjectId: $subject,
                owner: $owner
            }
        ) {
            __typename
        }
    }
"""

remove_membership_mutation = """
    mutation RemoveMembership($host: ID!, $subject: ID!) {
        removeMembership(
            input: {
                hostId: $host,
                subjectId: $subject
            }
        ) {
            __typename
        }
    }
"""

member_users_query = """
    query GetMemberUsers($host: ID!) {
        node(id: $host) {
            ...on MembershipHost {
                memberUsers(first: 100) {
                    edges {
                        node {
                            username
                        }
                        info {
                            isOwner
                        }
                    }
                }
            }
        }
    }
"""

user_membership_query = """
    query GetUserMembership($user: ID!, $host: ID!) {
        node(id: $user) {
            ...on User {
                membershipInfo(hostId: $host) {
                    isOwner
                }
            }
        }
    }
"""


@settings(max_examples=1)
@given(st.from_model(JoinableThing), st.superusers(), st.from_model(User))
def test_user_memberships(
    django_executor,
    graphql_client: Client,
    host: JoinableThing,
    superuser: User,
    subject: User,
):
    """Adding, modifying and removing a user's membership works as expected."""
    assume(superuser != subject)

    result = graphql_client.execute(
        set_membership_mutation,
        variables={
            "host": to_global_id(api.JoinableThing._meta.name, host.pk),
            "subject": to_global_id(accounts_api.User._meta.name, subject.pk),
            "owner": False,
        },
        context=FakeRequestContext(user=superuser),
    )
    assert "errors" not in result
    assert host.is_member(subject) and not host.is_owner(subject)

    result = graphql_client.execute(
        set_membership_mutation,
        variables={
            "host": to_global_id(api.JoinableThing._meta.name, host.pk),
            "subject": to_global_id(accounts_api.User._meta.name, subject.pk),
            "owner": True,
        },
        context=FakeRequestContext(user=superuser),
    )
    assert "errors" not in result
    assert host.is_owner(subject)

    result = graphql_client.execute(
        remove_membership_mutation,
        variables={
            "host": to_global_id(api.JoinableThing._meta.name, host.pk),
            "subject": to_global_id(accounts_api.User._meta.name, subject.pk),
        },
        context=FakeRequestContext(user=superuser),
    )
    assert "errors" not in result
    assert not host.is_member(subject) and not host.is_owner(subject)


@settings(max_examples=10)
@given(
    st.from_model(JoinableThing),
    st.superusers(),
    st.users(),
    st.users(),
    st.builds(AnonymousUser),
)
def test_permissions(
    django_executor,
    graphql_client: Client,
    host: JoinableThing,
    superuser: User,
    owner: User,
    member: User,
    anonymous: AnonymousUser,
):
    """Only owners and superusers may manage memberships."""
    assume(superuser != owner != member)

    host.add_user(owner, owner=True)
    host.add_user(member)

    def check_add_access(user: GenericUser, should_have_access: bool):
        result = graphql_client.execute(
            set_membership_mutation,
            variables={
                "host": to_global_id(api.JoinableThing._meta.name, host.pk),
                "subject": to_global_id(accounts_api.User._meta.name, superuser.pk),
                "owner": True,
            },
            context=FakeRequestContext(user=user),
        )
        if "errors" in result:
            assert len(result["errors"]) == 1
            assert "permission" in result["errors"][0]["message"]
            has_access = False
        else:
            has_access = True
        assert should_have_access is has_access

    check_add_access(anonymous, False)
    check_add_access(member, False)
    check_add_access(owner, True)
    check_add_access(superuser, True)

    def check_remove_access(
        user: GenericUser, subject: User, should_have_access: bool, **kwargs
    ):
        host.add_user(subject, **kwargs)
        result = graphql_client.execute(
            remove_membership_mutation,
            variables={
                "host": to_global_id(api.JoinableThing._meta.name, host.pk),
                "subject": to_global_id(accounts_api.User._meta.name, subject.pk),
            },
            context=FakeRequestContext(user=user),
        )
        if "errors" in result:
            assert len(result["errors"]) == 1
            assert "permission" in result["errors"][0]["message"]
            has_access = False
        else:
            has_access = True
        assert should_have_access is has_access

    check_remove_access(anonymous, superuser, False)
    check_remove_access(member, superuser, False)
    check_remove_access(owner, superuser, True)
    check_remove_access(superuser, member, True)
    # This last checks make sure that members can remove themselves.
    check_remove_access(owner, owner, True, owner=True)
    check_remove_access(member, member, True, owner=False)


@settings(max_examples=10)
@given(
    st.from_model(JoinableThing),
    st.superusers(),
    st.builds(AnonymousUser),
    st.sets(st.from_model(User), min_size=1, max_size=5),
    st.sets(st.from_model(User), min_size=1, max_size=5),
)
def test_member_users_query(
    django_executor,
    graphql_client: Client,
    host: JoinableThing,
    superuser: User,
    anonymous: AnonymousUser,
    non_owners: set[User],
    owners: set[User],
):
    # Make sure that all users are unique.
    assume(len(non_owners | owners) == len(non_owners) + len(owners))
    assume(superuser not in non_owners | owners)

    for user in non_owners:
        host.add_user(user)
    for user in owners:
        host.add_user(user, owner=True)

    variables = {"host": to_global_id(api.JoinableThing._meta.name, host.pk)}

    result = graphql_client.execute(
        member_users_query,
        variables=variables,
        context=FakeRequestContext(user=anonymous),
    )
    assert "errors" in result
    assert len(result["errors"]) == 1
    assert "permission" in result["errors"][0]["message"]

    result = graphql_client.execute(
        member_users_query,
        variables=variables,
        context=FakeRequestContext(user=superuser),
    )
    assert "errors" not in result

    edges = result["data"]["node"]["memberUsers"]["edges"]
    assert len(edges) == len(non_owners) + len(owners)
    for user in non_owners:
        assert {
            "info": {"isOwner": False},
            "node": {"username": user.username},
        } in edges
    for user in owners:
        assert {"info": {"isOwner": True}, "node": {"username": user.username}} in edges


@settings(max_examples=10)
@given(
    st.from_model(JoinableThing),
    st.superusers(),
    st.builds(AnonymousUser),
    st.from_model(User),
    st.from_model(User),
    st.booleans(),
)
def test_user_membership_query(
    django_executor,
    graphql_client: Client,
    host: JoinableThing,
    superuser: User,
    anonymous: AnonymousUser,
    user: User,
    watcher: User,
    owner: bool,
):
    assume(superuser != user and user != watcher)
    host.add_user(user, owner=owner)
    variables = {
        "host": to_global_id(api.JoinableThing._meta.name, host.pk),
        "user": to_global_id(api.User._meta.name, user.pk),
    }

    result = graphql_client.execute(
        user_membership_query,
        variables=variables,
        context=FakeRequestContext(user=superuser),
    )
    assert "errors" not in result
    assert result["data"]["node"]["membershipInfo"]["isOwner"] == owner

    result = graphql_client.execute(
        user_membership_query,
        variables=variables,
        context=FakeRequestContext(user=anonymous),
    )
    assert "errors" not in result
    assert result["data"]["node"] is None

    # Users may not see memberships of other users unless they are owner of the host.
    result = graphql_client.execute(
        user_membership_query,
        variables=variables,
        context=FakeRequestContext(user=watcher),
    )
    assert "errors" in result
    assert len(result["errors"]) == 1
    assert "permission" in result["errors"][0]["message"]

    host.add_user(watcher, owner=True)

    result = graphql_client.execute(
        user_membership_query,
        variables=variables,
        context=FakeRequestContext(user=watcher),
    )
    assert "errors" not in result
    assert result["data"]["node"]["membershipInfo"]["isOwner"] == owner
