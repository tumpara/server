import pytest
from django.db.models import Q
from graphene.relay.node import to_global_id
from graphene.test import Client
from hypothesis import given

from tumpara.accounts.models import AnonymousUser, GenericUser, User
from tumpara.testing import FakeRequestContext, FakeResolveInfo
from tumpara.testing import strategies as st

from . import api
from .models import Thing, ThingContainerMembers

organize_archive_mutation = """
    mutation OrganizeArchive($add: [ID!], $remove: [ID!]) {
        organizeArchive(
            input: {
                archiveIds: $add,
                unarchiveIds: $remove
            }
        ) {
            __typename
        }
    }
"""


@given(st.text())
def test_filterset(prefix):
    """The archiving filterset returns the correct values."""

    def filterset(include: bool, only: bool) -> api.ThingFilterSet:
        return api.ThingFilterSet._meta.container(
            {"include_archived": include, "only_archived": only}
        )

    assert filterset(False, False).build_query(FakeResolveInfo(), prefix) == Q(
        **{f"{prefix}archived": False}
    )
    assert filterset(True, False).build_query(FakeResolveInfo(), prefix) == Q()
    with pytest.raises(ValueError):
        filterset(True, True).build_query(FakeResolveInfo(), prefix)
    assert filterset(False, True).build_query(FakeResolveInfo(), prefix) == Q(
        **{f"{prefix}archived": True}
    )


@given(
    st.from_model(ThingContainerMembers, archived=st.just(False)),
    st.from_model(User),
    st.superusers(),
)
def test_permissions(
    django_executor,
    graphql_client: Client,
    thing: ThingContainerMembers,
    user: User,
    superuser: User,
):
    def check_access(user: GenericUser, should_have_access: bool):
        result = graphql_client.execute(
            organize_archive_mutation,
            variables={
                "add": [to_global_id(api.ThingContainerMembers._meta.name, thing.pk)]
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

    check_access(AnonymousUser(), False)
    check_access(user, False)
    thing.add_user(user, owner=True)
    check_access(user, True)
    check_access(superuser, True)


@given(
    st.lists(
        st.from_model(Thing, id=st.integers(1, 9999), archived=st.booleans()),
        min_size=2,
        max_size=20,
        unique=True,
    ),
    st.data(),
)
def test_archiving(
    django_executor, graphql_client: Client, things: list[Thing], data: st.DataObject
):
    """ "Archiving and unarchiving through the API works as expected."""
    archive_indexes = data.draw(st.sets(st.integers(0, len(things) - 1)))
    unarchive_indexes = set(range(len(things))) - archive_indexes

    result = graphql_client.execute(
        organize_archive_mutation,
        variables={
            "add": [
                to_global_id(api.Thing._meta.name, things[index].pk)
                for index in archive_indexes
            ],
            "remove": [
                to_global_id(api.Thing._meta.name, things[index].pk)
                for index in unarchive_indexes
            ],
        },
        context=FakeRequestContext(user=User.objects.create_superuser("superuser")),
    )
    if "errors" in result:
        assert "errors" not in result

    for thing in things:
        thing.refresh_from_db()
    for index in archive_indexes:
        assert things[index].archived is True
    for index in unarchive_indexes:
        assert things[index].archived is False
