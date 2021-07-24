import pytest
from django.core.exceptions import ValidationError
from django.db.models import Q
from graphene.relay.node import to_global_id
from graphene.test import Client
from hypothesis import assume, given

from tumpara.accounts.models import AnonymousUser, GenericUser, User
from tumpara.storage.models import Library
from tumpara.testing import FakeRequestContext, FakeResolveInfo
from tumpara.testing import strategies as st

from . import api
from tumpara.collections.api import CollectionsFilter
from .models import MaybeHiddenThing, Thing, ThingContainer, ThingContainerMembers


@given(
    st.from_model(ThingContainer),
    st.lists(
        st.from_model(Thing, id=st.integers(1, 9999)),
        min_size=2,
        max_size=20,
        unique=True,
    ),
    st.data(),
)
def test_adding(
    django_executor,
    graphql_client: Client,
    container: ThingContainer,
    things: list[Thing],
    data: st.DataObject,
):
    """The API successfully adds items to a collection."""
    assert container.items.count() == 0
    added_things = data.draw(st.sets(st.sampled_from(things), min_size=1))

    result = graphql_client.execute(
        """
            mutation AddThingsToContainer($ids: [ID!]!, $container: ID!) {
                organizeCollection(
                    input: {
                        collectionId: $container,
                        addItemIds: $ids
                    }
                ) {
                    __typename
                }
            }
        """,
        variables={
            "ids": [
                to_global_id(api.Thing._meta.name, thing.pk) for thing in added_things
            ],
            "container": to_global_id(api.ThingContainer._meta.name, container.pk),
        },
        context=FakeRequestContext(user=User.objects.create_superuser("superuser")),
    )
    assert "errors" not in result

    container_items = set(container.items.all())
    assert container_items == added_things


@given(
    st.from_model(ThingContainer),
    st.lists(
        st.from_model(Thing, id=st.integers(1, 9999)),
        min_size=2,
        max_size=20,
        unique=True,
    ),
    st.data(),
)
def test_removing(
    django_executor,
    graphql_client: Client,
    container: ThingContainer,
    things: list[Thing],
    data: st.DataObject,
):
    """The API successfully removes items from a collection."""
    assert container.items.count() == 0
    added_things = data.draw(st.sets(st.sampled_from(things), min_size=1))
    for thing in added_things:
        container.items.add(thing)
    assert container.items.count() == len(added_things)

    result = graphql_client.execute(
        """
            mutation RemoveThingsFromContainer($ids: [ID!]!, $container: ID!) {
                organizeCollection(
                    input: {
                        collectionId: $container,
                        removeItemIds: $ids
                    }
                ) {
                    __typename
                }
            }
        """,
        variables={
            "ids": [
                to_global_id(api.Thing._meta.name, thing.pk) for thing in added_things
            ],
            "container": to_global_id(api.ThingContainer._meta.name, container.pk),
        },
        context=FakeRequestContext(user=User.objects.create_superuser("superuser")),
    )
    assert "errors" not in result

    assert container.items.count() == 0


@pytest.mark.django_db
def test_permissions(graphql_client: Client):
    """Permission checking works as expected."""
    container: ThingContainerMembers = ThingContainerMembers.objects.create()

    anonymous = AnonymousUser()
    member = User.objects.create_user("member", "")
    owner = User.objects.create_user("owner", "")
    superuser = User.objects.create_superuser("superuser", "")
    container.add_user(member)
    container.add_user(owner, owner=True)

    def check_access(user: GenericUser, should_have_access: bool, container_id):
        result = graphql_client.execute(
            """
                mutation AddNothingToContainer($container: ID!) {
                    organizeCollection(
                        input: {
                            collectionId: $container,
                            addItemIds: []
                        }
                    ) {
                        __typename
                    }
                }
            """,
            variables={
                "container": container_id,
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

    # Ensure only owners and superusers may add / remove items for collections that
    # have the membership host mixin.
    container_id = to_global_id(api.ThingContainerMembers._meta.name, container.pk)
    check_access(anonymous, False, container_id)
    check_access(member, False, container_id)
    check_access(owner, True, container_id)
    check_access(superuser, True, container_id)

    # Ensure that all logged in users can edit
    container: ThingContainer = ThingContainer.objects.create()
    container_id = to_global_id(api.ThingContainer._meta.name, container.pk)
    check_access(anonymous, False, container_id)
    check_access(member, True, container_id)
    check_access(owner, True, container_id)
    check_access(superuser, True, container_id)


@pytest.mark.django_db
def test_invisible_thing(graphql_client: Client):
    """Items that are invisible (because the user is not a member of the
    corresponding library) cannot be added to a container."""
    user = User.objects.create_user("user")
    container = ThingContainer.objects.create()
    thing = MaybeHiddenThing.objects.create(
        library=Library.objects.create(context="testing", source="file://")
    )

    result = graphql_client.execute(
        """
            mutation AddThingToContainer($container: ID!, $thing: ID!) {
                organizeCollection(
                    input: {
                        collectionId: $container,
                        addItemIds: [$thing]
                    }
                ) {
                    __typename
                }
            }
        """,
        variables={
            "container": to_global_id(api.ThingContainer._meta.name, container.pk),
            "thing": to_global_id(api.MaybeHiddenThing._meta.name, thing.pk),
        },
        context=FakeRequestContext(user=user),
    )
    assert len(result["errors"]) == 1
    assert "permission" in result["errors"][0]["message"]


@given(
    st.from_model(ThingContainer),
    st.lists(
        st.from_model(Thing, id=st.integers(1, 9999)),
        min_size=2,
        max_size=10,
        unique=True,
    ),
    st.data(),
)
def test_twice_provided(
    django_executor,
    graphql_client: Client,
    container: ThingContainer,
    things: list[Thing],
    data: st.DataObject,
):
    """Simultaneously adding and removing an item returns an error."""
    added_things = data.draw(st.sets(st.sampled_from(things), min_size=1))
    removed_things = data.draw(st.sets(st.sampled_from(things), min_size=1))
    assume(len(added_things & removed_things) > 0)

    result = graphql_client.execute(
        """
            mutation AddAndRemoveItems($add: [ID!]!, $remove: [ID!]!, $container: ID!) {
                organizeCollection(
                    input: {
                        collectionId: $container,
                        addItemIds: $add,
                        removeItemIds: $remove
                    }
                ) {
                    __typename
                }
            }
        """,
        variables={
            "add": [
                to_global_id(api.Thing._meta.name, thing.pk) for thing in added_things
            ],
            "remove": [
                to_global_id(api.Thing._meta.name, thing.pk) for thing in removed_things
            ],
            "container": to_global_id(api.ThingContainer._meta.name, container.pk),
        },
        context=FakeRequestContext(user=User.objects.create_superuser("superuser")),
    )
    assert len(result["errors"]) == 1
    assert "both adding and removing" in result["errors"][0]["message"]


@given(st.from_model(ThingContainer))
def test_invalid_filter(django_executor, container: ThingContainer):
    """Invalid filter configurations throw a ValidationError."""
    with pytest.raises(ValidationError):
        container_id = to_global_id(api.ThingContainer._meta.name, container.pk)
        filter: CollectionsFilter = CollectionsFilter._meta.container(
            {"include": [container_id], "exclude": [container_id]}
        )
        filter.build_query(FakeResolveInfo(), "", ThingContainer, api.ThingContainer)


@given(
    st.field_prefix(),
    st.lists(
        st.from_model(ThingContainer, id=st.integers(1, 9999)),
        min_size=2,
        max_size=10,
        unique=True,
    ),
    st.data(),
)
def test_filter_both(
    django_executor, prefix: str, containers: list[ThingContainer], data: st.DataObject
):
    """Filtering for both 'inside' and 'not inside' works as expected."""
    include = data.draw(
        st.sets(st.sampled_from(containers), min_size=1, max_size=len(containers) - 1)
    )
    exclude = set(containers) - include

    filter: CollectionsFilter = CollectionsFilter._meta.container(
        {
            "include": [
                to_global_id(api.ThingContainer._meta.name, container.pk)
                for container in include
            ],
            "exclude": [
                to_global_id(api.ThingContainer._meta.name, container.pk)
                for container in exclude
            ],
        }
    )
    expected_query = Q(
        # Primary keys are cast to strings here because resolve_global_id() (which is
        # used by filter.build_query() below) doesn't bother with primary key types and
        # leaves them as strings, since Django handles that anyway.
        **{f"{prefix}__pk__in": set(str(container.pk) for container in include)}
    ) & ~Q(**{f"{prefix}__pk__in": set(str(container.pk) for container in exclude)})
    assert (
        filter.build_query(
            FakeResolveInfo(), prefix, ThingContainer, api.ThingContainer
        )
        == expected_query
    )


@given(
    st.field_prefix(),
    st.sets(
        st.from_model(ThingContainer, id=st.integers(1, 9999)),
        min_size=2,
        max_size=5,
    ),
    st.booleans(),
)
def test_filter_single(
    django_executor, prefix: str, containers: set[ThingContainer], negate: bool
):
    """Filtering for either 'include' or 'exclude' works as expected."""
    filter: CollectionsFilter = CollectionsFilter._meta.container(
        {
            ("exclude" if negate else "include"): [
                to_global_id(api.ThingContainer._meta.name, container.pk)
                for container in containers
            ],
        }
    )
    expected_query = Q(
        # Casting the primary key to string again, see the above test for details.
        **{f"{prefix}__pk__in": {str(container.pk) for container in containers}}
    )
    if negate:
        expected_query = ~expected_query
    assert (
        filter.build_query(
            FakeResolveInfo(), prefix, ThingContainer, api.ThingContainer
        )
        == expected_query
    )
