from hypothesis import given

from tests.test_storage.models import Thing
from tumpara.accounts.models import AnonymousUser, User
from tumpara.storage.models import Library
from tumpara.testing import strategies as st


def _setup_things(library: Library, data):
    public = {
        Thing.objects.create(library=library, visibility=Thing.PUBLIC)
        for _ in range(data.draw(st.integers(1, 5)))
    }
    internal = {
        Thing.objects.create(library=library, visibility=Thing.INTERNAL)
        for _ in range(data.draw(st.integers(1, 5)))
    }
    members = {
        Thing.objects.create(library=library, visibility=Thing.MEMBERS)
        for _ in range(data.draw(st.integers(1, 5)))
    }
    owners = {
        Thing.objects.create(library=library, visibility=Thing.OWNERS)
        for _ in range(data.draw(st.integers(1, 5)))
    }
    assert Thing.objects.count() == len(public | internal | members | owners)
    return public, internal, members, owners


@given(st.from_model(Library, source=st.just("test")), st.data())
def test_visibility_filtering(django_executor, library: Library, data: st.DataObject):
    """Visibility filtering for library content objects works as expected."""
    public, internal, members, owners = _setup_things(library, data)

    def check(thing_set: set[Thing], user, reading, writing):
        for thing in thing_set:
            assert thing.check_visibility(user) is reading
            assert thing.check_visibility(user, writing=True) is writing
        assert Thing.objects.bulk_check_visibility(user, thing_set) is reading
        assert (
            Thing.objects.bulk_check_visibility(user, thing_set, writing=True)
            is writing
        )

    anonymous = AnonymousUser()
    check(public, anonymous, True, False)
    check(internal | members | owners, anonymous, False, False)
    assert Thing.objects.for_user(anonymous).count() == len(public)
    assert Thing.objects.for_user(anonymous, writing=True).count() == 0

    other_user = User.objects.create_user("other")
    check(public | internal, other_user, True, False)
    check(members | owners, other_user, False, False)
    assert Thing.objects.for_user(other_user).count() == len(public | internal)
    assert Thing.objects.for_user(other_user, writing=True).count() == 0

    member = User.objects.create_user("member")
    library.add_user(member)
    check(public | internal | members, member, True, False)
    check(owners, member, False, False)
    assert Thing.objects.for_user(member).count() == len(public | internal | members)
    assert Thing.objects.for_user(member, writing=True).count() == 0

    full_set = public | internal | members | owners

    owner = User.objects.create_user("owner")
    library.add_user(owner, owner=True)
    check(full_set, owner, True, True)
    assert Thing.objects.for_user(owner).count() == len(full_set)
    assert Thing.objects.for_user(owner, writing=True).count() == len(full_set)

    superuser = User.objects.create_superuser("superuser")
    check(full_set, superuser, True, True)
    assert Thing.objects.for_user(superuser).count() == len(full_set)
    assert Thing.objects.for_user(superuser, writing=True).count() == len(full_set)
