from hypothesis import given

from tests.test_storage.models import Thing
from tumpara.accounts.models import AnonymousUser, User
from tumpara.storage.models import Library
from tumpara.testing import strategies as st


def _setup_things(library: Library, data):
    inferred = {
        Thing.objects.create(library=library, visibility=None)
        for _ in range(data.draw(st.integers(1, 5)))
    }
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
    assert Thing.objects.count() == len(inferred | public | internal | members | owners)
    return inferred, public, internal, members, owners


@given(
    st.from_model(
        Library,
        source=st.just("test"),
        default_visibility=st.from_field(Library.default_visibility.field),
    ),
    st.data(),
)
def test_visibility_filtering(django_executor, library: Library, data: st.DataObject):
    """Visibility filtering for library content objects works as expected."""
    inferred, public, internal, members, owners = _setup_things(library, data)

    if library.default_visibility == Library.PUBLIC:
        public |= inferred
    elif library.default_visibility == Library.INTERNAL:
        internal |= inferred
    elif library.default_visibility == Library.MEMBERS:
        members |= inferred
    elif library.default_visibility == Library.OWNERS:
        owners |= inferred
    inferred.clear()

    def check(thing_set: set[Thing], user, reading, writing):
        for thing in thing_set:
            assert thing.check_visibility(user) is reading
            assert thing.check_visibility(user, writing=True) is writing
        assert Thing.objects.bulk_check_visibility(user, thing_set) is reading
        assert (
            Thing.objects.bulk_check_visibility(user, thing_set, writing=True)
            is writing
        )

        if reading:
            assert Thing.objects.for_user(user).count() == len(thing_set)

        if writing:
            assert Thing.objects.for_user(user, writing=True).count() == len(thing_set)
        else:
            assert Thing.objects.for_user(user, writing=True).count() == 0

    anonymous = AnonymousUser()
    check(public, anonymous, True, False)
    check(internal | members | owners, anonymous, False, False)

    other_user = User.objects.create_user("other")
    check(public | internal, other_user, True, False)
    check(members | owners, other_user, False, False)

    member = User.objects.create_user("member")
    library.add_user(member)
    check(public | internal | members, member, True, False)
    check(owners, member, False, False)

    full_set = public | internal | members | owners

    owner = User.objects.create_user("owner")
    library.add_user(owner, owner=True)
    check(full_set, owner, True, True)

    superuser = User.objects.create_superuser("superuser")
    check(full_set, superuser, True, True)
