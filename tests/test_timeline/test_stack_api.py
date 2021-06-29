from graphene.relay.node import to_global_id
from graphene.test import Client
from hypothesis import HealthCheck, given, settings

from tumpara.accounts.models import AnonymousUser, GenericUser, User
from tumpara.testing import FakeRequestContext
from tumpara.testing import strategies as st
from tumpara.timeline.models import Entry

from . import api
from .models import BarEntry, FooEntry
from .test_entry_filtersets import dataset_strategy


@settings(
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
)
@given(dataset_strategy(), st.users(), st.data())
def test_stacking(
    django_executor,
    graphql_client: Client,
    entries: set[Entry],
    user: User,
    data: st.DataObject,
):
    """Stacking and unstacking a set of items works as expected."""
    node_ids = []
    for entry in entries:
        if isinstance(entry, FooEntry):
            node_ids.append(to_global_id(api.FooEntry._meta.name, entry.pk))
        elif isinstance(entry, BarEntry):
            node_ids.append(to_global_id(api.BarEntry._meta.name, entry.pk))

    def stack_result_for_user(test_user: GenericUser):
        return graphql_client.execute(
            """
                mutation Stack($ids: [ID!]!) {
                    stackTimelineEntries(input: { ids: $ids }) {
                        entries {
                            id
                            stackSize
                            stackRepresentative
                        }
                    }
                }
            """,
            variables={"ids": node_ids},
            context=FakeRequestContext(user=test_user),
        )

    def get_result(result_for_user):
        # Test both the user and anonymous to make sure that they can't update stacks
        # yet. Once the user is an owner, they should be able to stack entries.
        next(iter(entries)).library.add_user(user)

        for test_user in (user, AnonymousUser()):
            user_result = result_for_user(test_user)
            assert "errors" in user_result
            assert len(user_result["errors"]) == 1
            assert "permission" in user_result["errors"][0]["message"]

        next(iter(entries)).library.add_user(user, owner=True)

        user_result = result_for_user(user)
        assert "errors" not in user_result
        return user_result

    result = get_result(stack_result_for_user)
    result_entries = result["data"]["stackTimelineEntries"]["entries"]
    assert len(result_entries) == len(node_ids)
    for entry_result in result_entries:
        assert entry_result["stackSize"] == len(node_ids)
        assert entry_result["stackRepresentative"] is (
            entry_result["id"] == node_ids[0]
        )

    unstacked_id = data.draw(st.sampled_from(node_ids))

    def unstack_result_for_user(test_user: GenericUser):
        return graphql_client.execute(
            """
                mutation Unstack($id: ID!) {
                    unstackTimelineEntry(input: { id: $id }) {
                        entries {
                            id
                            stackSize
                            stackRepresentative
                        }
                    }
                }
            """,
            variables={"id": unstacked_id},
            context=FakeRequestContext(user=test_user),
        )

    result = get_result(unstack_result_for_user)
    result_entries = result["data"]["unstackTimelineEntry"]["entries"]
    assert len(result_entries) == len(node_ids)
    for entry_result in result_entries:
        if entry_result["id"] == unstacked_id:
            assert entry_result["stackSize"] == 1
            assert entry_result["stackRepresentative"] is False
        else:
            assert entry_result["stackSize"] == len(node_ids) - 1
    # Make sure there is only one representative (which should be a new one if
    # unstacked_id was the old representative).
    assert (
        len(
            [
                entry_result
                for entry_result in result_entries
                if entry_result["stackRepresentative"] is True
            ]
        )
        == 1
    )

    # Clear one of the IDs that hasn't been unstacked before.
    cleared_id = data.draw(
        st.sampled_from([node_id for node_id in node_ids if node_id != unstacked_id])
    )

    def clear_stack_result_for_user(test_user: GenericUser):
        return graphql_client.execute(
            """
                mutation Unstack($id: ID!) {
                    unstackTimelineEntry(input: { id: $id, clear: true }) {
                        entries {
                            id
                            stackSize
                            stackRepresentative
                        }
                    }
                }
            """,
            variables={"id": cleared_id},
            context=FakeRequestContext(user=test_user),
        )

    result = get_result(clear_stack_result_for_user)
    result_entries = result["data"]["unstackTimelineEntry"]["entries"]
    # After clearing the stack, we get one less entry returned (the one we unstacked
    # earlier).
    assert len(result_entries) == len(node_ids) - 1
    for entry_result in result_entries:
        assert entry_result["stackSize"] == 1
        assert entry_result["stackRepresentative"] is False
