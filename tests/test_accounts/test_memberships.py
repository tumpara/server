from typing import Set, Tuple

from hypothesis import given

from tumpara.accounts.models import AnonymousUser, User
from tumpara.testing import strategies as st

from .models import JoinableThing


def _setup_memberships(
    user: User, data
) -> Tuple[Set[JoinableThing], Set[JoinableThing], Set[JoinableThing]]:
    count = data.draw(st.integers(3, 30))
    member_id_set = data.draw(
        st.sets(st.integers(0, count - 1), min_size=2, max_size=count - 1)
    )
    owner_id_set = data.draw(
        st.sets(
            st.sampled_from(list(member_id_set)),
            min_size=1,
            max_size=len(member_id_set) - 1,
        )
    )

    owned = set()
    member = set()
    unrelated = set()

    for i in range(count):
        thing: JoinableThing = JoinableThing.objects.create(id=i)
        if i in owner_id_set:
            thing.add_user(user, owner=True)
            owned.add(thing)
        elif i in member_id_set:
            thing.add_user(user)
            member.add(thing)
        else:
            unrelated.add(thing)

    assert JoinableThing.objects.count() == count

    return owned, member, unrelated


@given(st.data())
def test_membership_checks(django_executor, data: st.DataObject):
    """Membership checking for a user and filtering based on membership works as
    intended."""
    user = User.objects.create_user("user")
    owned, member, unrelated = _setup_memberships(user, data)

    for thing in owned:
        assert thing.is_owner(user) is True
        assert thing.is_member(user) is True
    assert JoinableThing.objects.bulk_check_membership(user, owned) is True
    assert (
        JoinableThing.objects.bulk_check_membership(user, owned, ownership=True) is True
    )
    for thing in member:
        assert thing.is_owner(user) is False
        assert thing.is_member(user) is True
    assert JoinableThing.objects.bulk_check_membership(user, member) is True
    assert (
        JoinableThing.objects.bulk_check_membership(user, member, ownership=True)
        is False
    )
    for thing in unrelated:
        assert thing.is_owner(user) is False
        assert thing.is_member(user) is False
    assert JoinableThing.objects.bulk_check_membership(user, unrelated) is False

    assert JoinableThing.objects.for_user(user, ownership=True).count() == len(owned)
    assert JoinableThing.objects.owned_by(user).count() == len(owned)
    assert JoinableThing.objects.for_user(user, ownership=False).count() == len(member)
    assert JoinableThing.objects.for_user(user).count() == len(owned | member)

    anonymous = AnonymousUser()
    superuser = User.objects.create_superuser("superuser")

    for thing in owned | member | unrelated:
        assert thing.is_owner(anonymous) is False
        assert thing.is_member(anonymous) is False
        assert thing.is_owner(superuser) is True
        assert thing.is_member(superuser) is True
    assert JoinableThing.objects.bulk_check_membership(anonymous, owned) is False
    assert JoinableThing.objects.bulk_check_membership(anonymous, member) is False
    assert JoinableThing.objects.bulk_check_membership(anonymous, unrelated) is False
    assert JoinableThing.objects.bulk_check_membership(superuser, owned) is True
    assert JoinableThing.objects.bulk_check_membership(superuser, member) is True
    assert JoinableThing.objects.bulk_check_membership(superuser, unrelated) is True

    assert JoinableThing.objects.for_user(anonymous).count() == 0
    assert JoinableThing.objects.for_user(superuser).count() == len(
        owned | member | unrelated
    )
