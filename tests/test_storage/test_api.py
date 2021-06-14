from functools import reduce

from graphene.relay.node import to_global_id
from graphene.test import Client
from hypothesis import assume, given

from tumpara.accounts.models import AnonymousUser, GenericUser, User
from tumpara.storage.models import Library
from tumpara.testing import FakeRequestContext
from tumpara.testing import strategies as st

from . import api
from .models import Thing
from .test_librarycontent import _setup_things

organize_library_content_mutation = """
    mutation OrganizeLibraryContent($ids: [ID!]!, $visibility: LibraryContentVisibility) {
        organizeLibraryContent(input: {
            ids: $ids,
            visibility: $visibility,
        }) {
            nodes {
                id
            }
        }
    }
"""


@given(
    st.from_model(Library, source=st.just("test")),
    st.from_model(User),
    st.superusers(),
    st.data(),
)
def test_organize_library_content(
    django_executor,
    graphql_client: Client,
    library: Library,
    test_user: User,
    superuser: User,
    data: st.DataObject,
):
    """Visibility filtering for library content objects works as expected."""
    assume(test_user != superuser)

    things: set[Thing] = set(reduce(set.union, _setup_things(library, data)))

    def check(
        user: GenericUser,
        visibility: int,
        api_visibility: str,
        should_have_access: bool,
    ):
        result = graphql_client.execute(
            organize_library_content_mutation,
            variables={
                "ids": [
                    to_global_id(api.Thing._meta.name, thing.pk) for thing in things
                ],
                "visibility": api_visibility,
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

        if has_access:
            for thing in things:
                thing.refresh_from_db()
                assert thing.visibility == visibility

    check(AnonymousUser(), Thing.PUBLIC, "PUBLIC", False)
    check(test_user, Thing.MEMBERS, "MEMBERS", False)
    library.add_user(test_user)
    check(test_user, Thing.MEMBERS, "MEMBERS", False)
    library.add_user(test_user, owner=True)
    check(test_user, Thing.MEMBERS, "MEMBERS", True)
    check(superuser, Thing.OWNERS, "OWNERS", True)
