import os.path
from datetime import datetime, timedelta
from functools import reduce

import pytest
from django.test import Client as DjangoClient
from freezegun import freeze_time
from graphene.relay.node import to_global_id
from graphene.test import Client as GrapheneClient
from hypothesis import assume, given, settings

from tumpara.accounts.models import AnonymousUser, GenericUser, User
from tumpara.storage.models import Library
from tumpara.testing import FakeRequestContext
from tumpara.testing import strategies as st

from . import api
from .models import GenericFileHandler, Thing
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
    graphql_client: GrapheneClient,
    library: Library,
    test_user: User,
    superuser: User,
    data: st.DataObject,
):
    """Organizing library content visibility works through the API."""
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


@pytest.mark.filterwarnings("ignore")
@settings(deadline=1000)
@given(
    st.temporary_directories(),
    st.dictionaries(
        st.filenames(), st.binary(min_size=1, max_size=20 * 1024 * 1204), min_size=1
    ),
)
def test_file_downloading(
    django_executor,
    graphql_client: GrapheneClient,
    root: str,
    file_data: dict[str, bytes],
):
    """Users are able to obtain working file download links from the API."""
    library = Library.objects.create(context="testing", source=f"file://{root}")

    for filename, content in file_data.items():
        with open(os.path.join(root, filename), "wb") as f:
            f.write(content)
    library.scan()

    assert GenericFileHandler.objects.count() == len(file_data)
    client = DjangoClient()

    for filename, content in file_data.items():
        handler = GenericFileHandler.objects.get(file__path=filename)

        result = graphql_client.execute(
            """
                query GetFileUrl($id: ID!) {
                    node(id: $id) {
                        ...on File {
                            fileUrl
                        }
                    }
                }
            """,
            variables={"id": to_global_id(api.GenericFile._meta.name, handler.pk)},
        )
        assert "errors" not in result
        url = result["data"]["node"]["fileUrl"]

        response = client.get(url)
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == content

        with freeze_time(datetime.now() + timedelta(hours=1, seconds=2)):
            response = client.get(url)
            assert response.status_code == 404
