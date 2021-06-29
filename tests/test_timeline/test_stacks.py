import pytest
from django.core.exceptions import PermissionDenied
from hypothesis import HealthCheck, assume, given, settings

from tumpara.accounts.models import AnonymousUser, User
from tumpara.testing import strategies as st
from tumpara.timeline.models import Entry

from .test_entry_filtersets import dataset_strategy


@settings(
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
)
@given(
    dataset_strategy(),
    st.from_model(User, is_superuser=st.just(False)),
    st.superusers(),
    st.data(),
)
def test_stacking(
    django_executor,
    entries: set[Entry],
    user: User,
    superuser: User,
    data: st.DataObject,
):
    assume(user != superuser)

    first_stack: set[Entry] = data.draw(
        st.sets(st.sampled_from(list(entries)), min_size=2, max_size=len(entries) - 3)
    )
    not_stacked_entries: set[Entry] = entries - first_stack
    second_stack: set[Entry] = data.draw(
        st.sets(
            st.sampled_from(list(not_stacked_entries)),
            min_size=2,
            max_size=len(not_stacked_entries) - 1,
        )
    )
    not_stacked_entries -= second_stack

    first_stack: list[Entry] = list(first_stack)
    second_stack: list[Entry] = list(second_stack)

    # Get the visibility values each stack should receive. This is the most private one
    # among the present values.
    first_stack_visibility = max(
        first_stack, key=lambda entry: entry.visibility
    ).visibility
    second_stack_visibility = max(
        second_stack, key=lambda entry: entry.visibility
    ).visibility

    # Check that permissions are evaluated correctly
    with pytest.raises(PermissionDenied):
        Entry.objects.stack(first_stack, requester=AnonymousUser())
    with pytest.raises(PermissionDenied):
        Entry.objects.stack(first_stack, requester=user)
    first_stack[0].library.add_user(user)
    with pytest.raises(PermissionDenied):
        Entry.objects.stack(first_stack, requester=user)

    # Perform the actual stacking
    first_stack[0].library.add_user(user, owner=True)
    Entry.objects.stack(first_stack, requester=user)
    Entry.objects.stack((entry.pk for entry in second_stack), requester=superuser)
    for entry in entries:
        entry.refresh_from_db()

    first_stack_key = first_stack[0].stack_key
    assert first_stack_key is not None
    for entry in first_stack:
        assert entry.stack_key == first_stack_key
        assert entry.stack_representative is (entry is first_stack[0])
        # assert entry.stack_representative is False
        assert entry.visibility == first_stack_visibility
        assert entry.stack_size == len(first_stack)

    second_stack_key = second_stack[0].stack_key
    assert second_stack_key is not None
    for entry in second_stack:
        assert entry.stack_key == second_stack_key
        assert entry.stack_representative is (entry is second_stack[0])
        # assert entry.stack_representative is False
        assert entry.visibility == second_stack_visibility
        assert entry.stack_size == len(second_stack)

    assert first_stack_key != second_stack_key


@settings(
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
)
@given(
    dataset_strategy(),
    st.from_model(User),
    st.superusers(),
)
def test_stack_clearing(
    django_executor,
    entries: set[Entry],
    user: User,
    superuser: User,
):
    assume(user != superuser)
    entries: list[Entry] = list(entries)

    Entry.objects.stack(entries)
    for entry in entries:
        entry.refresh_from_db()

    stack_key = entries[0].stack_key
    assert entries[0].stack_size == len(entries)
    for entry in entries:
        assert entry.stack_key == stack_key
        assert entry.stack_representative is (entry is entries[0])

    # Check that permissions are evaluated correctly
    with pytest.raises(PermissionDenied):
        entries[0].clear_stack(requester=AnonymousUser())
    with pytest.raises(PermissionDenied):
        entries[0].clear_stack(requester=user)
    entries[0].library.add_user(user)
    with pytest.raises(PermissionDenied):
        entries[0].clear_stack(requester=user)

    entries[0].library.add_user(user, owner=True)
    entries[0].clear_stack(requester=user)

    for entry in entries:
        entry.refresh_from_db()
        assert entry.stack_key is None
        assert entry.stack_representative is False
        assert entry.stack_size == 1


@settings(
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
)
@given(
    dataset_strategy(min_size=2, max_size=5),
    st.from_model(User),
    st.superusers(),
)
def test_unstacking(
    django_executor,
    entries: set[Entry],
    user: User,
    superuser: User,
):
    assume(user != superuser)
    entries: list[Entry] = list(entries)

    Entry.objects.stack(entries)
    for entry in entries:
        entry.refresh_from_db()

    stack_key = entries[0].stack_key
    stack_size_before = entries[0].stack_size
    assert entries[0].stack_representative is True

    # Check that permissions are evaluated correctly
    with pytest.raises(PermissionDenied):
        entries[0].unstack(requester=AnonymousUser())
    with pytest.raises(PermissionDenied):
        entries[0].unstack(requester=user)
    entries[0].library.add_user(user)
    with pytest.raises(PermissionDenied):
        entries[0].unstack(requester=user)

    entries[0].library.add_user(user, owner=True)
    entries[0].unstack(requester=user)

    # Make sure the first entry (the one we unstacked) is no longer in the stack.
    assert entries[0].stack_key is None
    assert entries[0].stack_representative is False
    assert entries[0].stack_size == 1

    if len(entries) == 2:
        # If we only had two items in the stack, the stack should now be completely
        # cleared.
        entries[1].refresh_from_db()
        assert entries[1].stack_key is None
        assert entries[1].stack_representative is False
        assert entries[1].stack_size == 1
    else:
        # If the stack was larger, all other entries should still be in the stack.
        for entry in entries[1:]:
            entry.refresh_from_db()
            assert entry.stack_key == stack_key
            assert entry.stack_size == stack_size_before - 1

        # There should be a new representative, which preferably should not be
        # archived if possible.
        representatives = [entry for entry in entries[1:] if entry.stack_representative]
        assert len(representatives) == 1
        if any(not entry.archived for entry in entries[1:]):
            assert representatives[0].archived is False
